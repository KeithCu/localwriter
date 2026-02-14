import sys
import os

# Ensure extension directory is on path so streaming_deltas can be imported
_ext_dir = os.path.dirname(os.path.abspath(__file__))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

import unohelper
import officehelper
import json

from core.config import get_config, set_config, as_bool, get_api_config
from core.api import LlmClient
from core.document import get_full_document_text
from core.logging import log_to_file
from core.constants import DEFAULT_CHAT_SYSTEM_PROMPT
from com.sun.star.task import XJobExecutor
from com.sun.star.awt import MessageBoxButtons as MSG_BUTTONS
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK
import uno
import logging
import re

from com.sun.star.beans import PropertyValue
from com.sun.star.container import XNamed

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/114.0.0.0 Safari/537.36'
)

# Use workspace path so logs are readable when extension runs from LibreOffice install
DEBUG_LOG_PATH = "/home/keithcu/Desktop/Python/localwriter/.cursor/debug.log"


# The MainJob is a UNO component derived from unohelper.Base class
# and also the XJobExecutor, the implemented interface
class MainJob(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx
        # handling different situations (inside LibreOffice or other process)
        try:
            self.sm = ctx.getServiceManager()
            self.desktop = XSCRIPTCONTEXT.getDesktop()
            self.document = XSCRIPTCONTEXT.getDocument()
        except NameError:
            self.sm = ctx.ServiceManager
            self.desktop = self.ctx.getServiceManager().createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
    

    def get_config(self, key, default):
        """Delegate to core.config. Kept for API compatibility (chat_panel, etc.)."""
        return get_config(self.ctx, key, default)

    def set_config(self, key, value):
        """Delegate to core.config."""
        set_config(self.ctx, key, value)

    def _get_client(self):
        """Create LlmClient with current config."""
        config = get_api_config(self.ctx)
        return LlmClient(config, self.ctx)

    def show_error(self, message, title="LocalWriter Error"):
        """Show an error message in a dialog instead of writing to the document."""
        try:
            desktop = self.sm.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
            frame = desktop.getCurrentFrame()
            if frame and frame.ActiveFrame:
                frame = frame.ActiveFrame
            window_peer = frame.getContainerWindow() if frame else None
            if window_peer:
                toolkit = self.sm.createInstanceWithContext(
                    "com.sun.star.awt.Toolkit", self.ctx)
                box = toolkit.createMessageBox(window_peer, ERRORBOX, BUTTONS_OK, title, str(message))
                box.execute()
        except Exception:
            pass  # Fallback: if dialog fails, at least we don't crash

    def stream_completion(
        self,
        prompt,
        system_prompt,
        max_tokens,
        api_type,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Single entry point for streaming completions. Raises on error."""
        self._get_client().stream_completion(
            prompt,
            system_prompt,
            max_tokens,
            api_type,
            append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def make_chat_request(self, messages, max_tokens=512, tools=None, stream=False):
        """Delegate to LlmClient."""
        return self._get_client().make_chat_request(
            messages, max_tokens, tools=tools, stream=stream
        )

    def request_with_tools(self, messages, max_tokens=512, tools=None):
        """Delegate to LlmClient."""
        return self._get_client().request_with_tools(
            messages, max_tokens, tools=tools
        )

    def stream_request_with_tools(
        self,
        messages,
        max_tokens=512,
        tools=None,
        append_callback=None,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Delegate to LlmClient."""
        return self._get_client().stream_request_with_tools(
            messages,
            max_tokens,
            tools=tools,
            append_callback=append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def stream_chat_response(
        self,
        messages,
        max_tokens,
        append_callback,
        append_thinking_callback=None,
        stop_checker=None,
    ):
        """Delegate to LlmClient."""
        self._get_client().stream_chat_response(
            messages,
            max_tokens,
            append_callback,
            append_thinking_callback=append_thinking_callback,
            stop_checker=stop_checker,
        )

    def get_full_document_text(self, model, max_chars=8000):
        """Delegate to core.document."""
        return get_full_document_text(model, max_chars)

    def input_box(self, message, title="", default="", x=None, y=None):
        """ Shows input dialog (EditInputDialog.xdl). Returns edit text if OK, else "". """
        import uno
        ctx = self.ctx
        smgr = ctx.getServiceManager()
        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dlg = dp.createDialog(base_url + "/LocalWriterDialogs/EditInputDialog.xdl")
        try:
            dlg.getControl("label").getModel().Label = str(message)
            dlg.getControl("edit").getModel().Text = str(default)
            if title:
                dlg.getModel().Title = title
            dlg.getControl("edit").setFocus()
            dlg.getControl("edit").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(str(default))))
            ret = dlg.getControl("edit").getModel().Text if dlg.execute() else ""
        finally:
            dlg.dispose()
        return ret

    def settings_box(self, title="", x=None, y=None):
        """ Settings dialog loaded from XDL (LocalWriterDialogs/SettingsDialog.xdl).
        Uses DialogProvider for proper Map AppFont sizing. """
        # #region agent log
        try:
            _log = open(DEBUG_LOG_PATH, "a")
            _log.write('{"location":"main.py:settings_box","message":"settings_box entered","data":{},"hypothesisId":"H3,H4","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
            _log.close()
        except Exception:
            pass
        # #endregion
        import uno
        ctx = self.ctx
        smgr = ctx.getServiceManager()

        openai_compatibility_value = "true" if as_bool(self.get_config("openai_compatibility", False)) else "false"
        is_openwebui_value = "true" if as_bool(self.get_config("is_openwebui", False)) else "false"
        field_specs = [
            {"name": "endpoint", "value": str(self.get_config("endpoint", "http://127.0.0.1:5000"))},
            {"name": "model", "value": str(self.get_config("model", ""))},
            {"name": "api_key", "value": str(self.get_config("api_key", ""))},
            {"name": "api_type", "value": str(self.get_config("api_type", "completions"))},
            {"name": "is_openwebui", "value": is_openwebui_value, "type": "bool"},
            {"name": "openai_compatibility", "value": openai_compatibility_value, "type": "bool"},
            {"name": "temperature", "value": str(self.get_config("temperature", "0.5")), "type": "float"},
            {"name": "seed", "value": str(self.get_config("seed", ""))},
            {"name": "extend_selection_max_tokens", "value": str(self.get_config("extend_selection_max_tokens", "70")), "type": "int"},
            {"name": "extend_selection_system_prompt", "value": str(self.get_config("extend_selection_system_prompt", ""))},
            {"name": "edit_selection_max_new_tokens", "value": str(self.get_config("edit_selection_max_new_tokens", "0")), "type": "int"},
            {"name": "edit_selection_system_prompt", "value": str(self.get_config("edit_selection_system_prompt", ""))},
            {"name": "chat_max_tokens", "value": str(self.get_config("chat_max_tokens", "16384")), "type": "int"},
            {"name": "chat_context_length", "value": str(self.get_config("chat_context_length", "8000")), "type": "int"},
            {"name": "chat_system_prompt", "value": str(self.get_config("chat_system_prompt", "") or DEFAULT_CHAT_SYSTEM_PROMPT)},
            {"name": "request_timeout", "value": str(self.get_config("request_timeout", "120")), "type": "int"},
        ]

        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        # #region agent log
        try:
            _log = open(DEBUG_LOG_PATH, "a")
            _log.write('{"location":"main.py:settings_box","message":"before createDialog","data":{},"hypothesisId":"H3","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
            _log.close()
        except Exception:
            pass
        # #endregion
        try:
            dlg = dp.createDialog(base_url + "/LocalWriterDialogs/SettingsDialog.xdl")
        except BaseException as ex:
            # #region agent log
            try:
                _log = open(DEBUG_LOG_PATH, "a")
                _log.write('{"location":"main.py:settings_box","message":"createDialog failed","data":{"error":%s,"type":%s},"hypothesisId":"H3","timestamp":%d}\n' % (json.dumps(str(ex)), json.dumps(type(ex).__name__), int(__import__("time").time() * 1000)))
                _log.close()
            except Exception:
                pass
            # #endregion
            raise
        finally:
            # #region agent log
            try:
                _log = open(DEBUG_LOG_PATH, "a")
                _log.write('{"location":"main.py:settings_box","message":"createDialog block exited","data":{},"hypothesisId":"H3","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
                _log.close()
            except Exception:
                pass
            # #endregion
        # #region agent log
        try:
            _log = open(DEBUG_LOG_PATH, "a")
            _log.write('{"location":"main.py:settings_box","message":"createDialog succeeded","data":{},"hypothesisId":"H3","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
            _log.close()
        except Exception:
            pass
        # #endregion
        try:
            for field in field_specs:
                ctrl = dlg.getControl(field["name"])
                if ctrl:
                    ctrl.getModel().Text = field["value"]
            dlg.getControl("endpoint").setFocus()
            # #region agent log
            try:
                _log = open(DEBUG_LOG_PATH, "a")
                _log.write('{"location":"main.py:settings_box","message":"before dlg.execute","data":{},"hypothesisId":"H4","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
                _log.close()
            except Exception:
                pass
            # #endregion
            exec_result = dlg.execute()
            # #region agent log
            try:
                _log = open(DEBUG_LOG_PATH, "a")
                _log.write('{"location":"main.py:settings_box","message":"after dlg.execute","data":{"exec_result":%s},"hypothesisId":"H4","timestamp":%d}\n' % (str(exec_result), int(__import__("time").time() * 1000)))
                _log.close()
            except Exception:
                pass
            # #endregion
            if exec_result:
                result = {}
                for field in field_specs:
                    ctrl = dlg.getControl(field["name"])
                    control_text = ctrl.getModel().Text if ctrl else ""
                    field_type = field.get("type", "text")
                    if field_type == "int":
                        result[field["name"]] = int(control_text) if control_text.isdigit() else control_text
                    elif field_type == "bool":
                        result[field["name"]] = as_bool(control_text)
                    elif field_type == "float":
                        try:
                            result[field["name"]] = float(control_text)
                        except ValueError:
                            result[field["name"]] = control_text
                    else:
                        result[field["name"]] = control_text
            else:
                result = {}
        finally:
            dlg.dispose()
        return result

    def trigger(self, args):
        # #region agent log
        try:
            _log = open(DEBUG_LOG_PATH, "a")
            _log.write('{"location":"main.py:trigger","message":"trigger called","data":{"args":%s},"hypothesisId":"H1,H2","timestamp":%d}\n' % (json.dumps(str(args)), int(__import__("time").time() * 1000)))
            _log.close()
        except Exception:
            pass
        # #endregion
        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)
        model = desktop.getCurrentComponent()
        # #region agent log
        try:
            _log = open(DEBUG_LOG_PATH, "a")
            _log.write('{"location":"main.py:trigger","message":"model state","data":{"model_is_none":%s,"has_text":%s,"has_sheets":%s},"hypothesisId":"H2","timestamp":%d}\n' % (str(model is None), str(hasattr(model, "Text") if model else False), str(hasattr(model, "Sheets") if model else False), int(__import__("time").time() * 1000)))
            _log.close()
        except Exception:
            pass
        # #endregion
        #if not hasattr(model, "Text"):
        #    model = self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())

        if args == "settings" and (not model or (not hasattr(model, "Text") and not hasattr(model, "Sheets"))):
            # #region agent log
            try:
                _log = open(DEBUG_LOG_PATH, "a")
                _log.write('{"location":"main.py:trigger","message":"settings requested but no Writer/Calc document","data":{"args":%s},"hypothesisId":"H2","timestamp":%d}\n' % (json.dumps(str(args)), int(__import__("time").time() * 1000)))
                _log.close()
            except Exception:
                pass
            # #endregion
        if hasattr(model, "Text"):
            text = model.Text
            selection = model.CurrentController.getSelection()
            text_range = selection.getByIndex(0)

            
            if args == "ExtendSelection":
                # Access the current selection
                if len(text_range.getString()) > 0:
                    try:
                        system_prompt = self.get_config("extend_selection_system_prompt", "")
                        prompt = text_range.getString()
                        max_tokens = self.get_config("extend_selection_max_tokens", 70)
                        api_type = str(self.get_config("api_type", "completions")).lower()

                        def append_text(chunk_text):
                            text_range.setString(text_range.getString() + chunk_text)

                        self.stream_completion(prompt, system_prompt, max_tokens, api_type, append_text)
                    except Exception as e:
                        self.show_error(str(e), "LocalWriter: Extend Selection")

            elif args == "EditSelection":
                # Access the current selection
                original_text = text_range.getString()
                try:
                    user_input = self.input_box("Please enter edit instructions!", "Input", "")
                    if not user_input:
                        return
                    
                    prompt = "ORIGINAL VERSION:\n" + original_text + "\n Below is an edited version according to the following instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                    system_prompt = self.get_config("edit_selection_system_prompt", "")
                    max_tokens = len(original_text) + self.get_config("edit_selection_max_new_tokens", 0)
                    api_type = str(self.get_config("api_type", "completions")).lower()
                    
                    text_range.setString("")

                    def append_text(chunk_text):
                        text_range.setString(text_range.getString() + chunk_text)

                    self.stream_completion(prompt, system_prompt, max_tokens, api_type, append_text)
                except Exception as e:
                    text_range.setString(original_text)  # Restore original on failure
                    self.show_error(str(e), "LocalWriter: Edit Selection")

            elif args == "ChatWithDocument":
                try:
                    max_context = int(self.get_config("chat_context_length", 8000))
                    doc_text = self.get_full_document_text(model, max_context)
                    if not doc_text.strip():
                        self.show_error("Document is empty.", "Chat with Document")
                        return
                    user_query = self.input_box("Ask a question about your document:", "Chat with Document", "")
                    if not user_query:
                        return
                    prompt = f"Document content:\n\n{doc_text}\n\nUser question: {user_query}"
                    system_prompt = self.get_config("chat_system_prompt", "") or DEFAULT_CHAT_SYSTEM_PROMPT
                    max_tokens = int(self.get_config("chat_max_tokens", 512))
                    api_type = str(self.get_config("api_type", "completions")).lower()
                    text = model.Text
                    cursor = text.createTextCursor()
                    cursor.gotoEnd(False)
                    cursor.insertString("\n\n--- Chat response ---\n\n", False)

                    def append_chunk(chunk_text):
                        cursor.insertString(chunk_text, False)

                    self.stream_completion(prompt, system_prompt, max_tokens, api_type, append_chunk)
                except Exception as e:
                    self.show_error(str(e), "LocalWriter: Chat with Document")
            
            elif args == "settings":
                try:
                    # #region agent log
                    try:
                        _log = open(DEBUG_LOG_PATH, "a")
                        _log.write('{"location":"main.py:trigger","message":"about to call settings_box (Writer)","data":{},"hypothesisId":"H1,H2","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
                        _log.close()
                    except Exception:
                        pass
                    # #endregion
                    result = self.settings_box("Settings")
                                    
                    if "extend_selection_max_tokens" in result:
                        self.set_config("extend_selection_max_tokens", result["extend_selection_max_tokens"])

                    if "extend_selection_system_prompt" in result:
                        self.set_config("extend_selection_system_prompt", result["extend_selection_system_prompt"])

                    if "edit_selection_max_new_tokens" in result:
                        self.set_config("edit_selection_max_new_tokens", result["edit_selection_max_new_tokens"])

                    if "edit_selection_system_prompt" in result:
                        self.set_config("edit_selection_system_prompt", result["edit_selection_system_prompt"])

                    if "endpoint" in result and result["endpoint"].startswith("http"):
                        self.set_config("endpoint", result["endpoint"])

                    if "api_key" in result:
                        self.set_config("api_key", result["api_key"])

                    if "api_type" in result:
                        api_type_value = str(result["api_type"]).strip().lower()
                        if api_type_value not in ("chat", "completions"):
                            api_type_value = "completions"
                        self.set_config("api_type", api_type_value)

                    if "is_openwebui" in result:
                        self.set_config("is_openwebui", result["is_openwebui"])

                    if "openai_compatibility" in result:
                        self.set_config("openai_compatibility", result["openai_compatibility"])

                    if "model" in result:                
                        self.set_config("model", result["model"])
                        
                    if "temperature" in result:                
                        self.set_config("temperature", result["temperature"])
                        
                    if "seed" in result:                
                        self.set_config("seed", result["seed"])

                    if "chat_max_tokens" in result:
                        self.set_config("chat_max_tokens", result["chat_max_tokens"])

                    if "chat_context_length" in result:
                        self.set_config("chat_context_length", result["chat_context_length"])

                    if "chat_system_prompt" in result:
                        self.set_config("chat_system_prompt", result["chat_system_prompt"])

                    if "request_timeout" in result:
                        self.set_config("request_timeout", result["request_timeout"])


                except Exception as e:
                    # #region agent log
                    try:
                        _log = open(DEBUG_LOG_PATH, "a")
                        _log.write('{"location":"main.py:trigger","message":"settings exception (Writer)","data":{"error":%s},"hypothesisId":"H5","timestamp":%d}\n' % (json.dumps(str(e)), int(__import__("time").time() * 1000)))
                        _log.close()
                    except Exception:
                        pass
                    # #endregion
                    self.show_error(str(e), "LocalWriter: Settings")
        elif hasattr(model, "Sheets"):
            try:
                if args == "ChatWithDocument":
                    self.show_error("Chat with Document is only available in Writer.", "LocalWriter")
                    return
                sheet = model.CurrentController.ActiveSheet
                selection = model.CurrentController.Selection

                if args == "settings":
                    try:
                        # #region agent log
                        try:
                            _log = open(DEBUG_LOG_PATH, "a")
                            _log.write('{"location":"main.py:trigger","message":"about to call settings_box (Calc)","data":{},"hypothesisId":"H1,H2","timestamp":%d}\n' % (int(__import__("time").time() * 1000)))
                            _log.close()
                        except Exception:
                            pass
                        # #endregion
                        result = self.settings_box("Settings")
                                        
                        if "extend_selection_max_tokens" in result:
                            self.set_config("extend_selection_max_tokens", result["extend_selection_max_tokens"])

                        if "extend_selection_system_prompt" in result:
                            self.set_config("extend_selection_system_prompt", result["extend_selection_system_prompt"])

                        if "edit_selection_max_new_tokens" in result:
                            self.set_config("edit_selection_max_new_tokens", result["edit_selection_max_new_tokens"])

                        if "edit_selection_system_prompt" in result:
                            self.set_config("edit_selection_system_prompt", result["edit_selection_system_prompt"])

                        if "endpoint" in result and result["endpoint"].startswith("http"):
                            self.set_config("endpoint", result["endpoint"])

                        if "api_key" in result:
                            self.set_config("api_key", result["api_key"])

                        if "api_type" in result:
                            api_type_value = str(result["api_type"]).strip().lower()
                            if api_type_value not in ("chat", "completions"):
                                api_type_value = "completions"
                            self.set_config("api_type", api_type_value)

                        if "is_openwebui" in result:
                            self.set_config("is_openwebui", result["is_openwebui"])

                        if "openai_compatibility" in result:
                            self.set_config("openai_compatibility", result["openai_compatibility"])

                        if "model" in result:                
                            self.set_config("model", result["model"])

                        if "temperature" in result:                
                            self.set_config("temperature", result["temperature"])

                        if "seed" in result:                
                            self.set_config("seed", result["seed"])

                        if "chat_max_tokens" in result:
                            self.set_config("chat_max_tokens", result["chat_max_tokens"])

                        if "chat_context_length" in result:
                            self.set_config("chat_context_length", result["chat_context_length"])

                        if "chat_system_prompt" in result:
                            self.set_config("chat_system_prompt", result["chat_system_prompt"])
                    except Exception as e:
                        # #region agent log
                        try:
                            _log = open(DEBUG_LOG_PATH, "a")
                            _log.write('{"location":"main.py:trigger","message":"settings exception (Calc)","data":{"error":%s},"hypothesisId":"H5","timestamp":%d}\n' % (json.dumps(str(e)), int(__import__("time").time() * 1000)))
                            _log.close()
                        except Exception:
                            pass
                        # #endregion
                        self.show_error(str(e), "LocalWriter: Settings")
                    return

                user_input = ""
                if args == "EditSelection":
                    user_input = self.input_box("Please enter edit instructions!", "Input", "")

                area = selection.getRangeAddress()
                start_row = area.StartRow
                end_row = area.EndRow
                start_col = area.StartColumn
                end_col = area.EndColumn

                col_range = range(start_col, end_col + 1)
                row_range = range(start_row, end_row + 1)

                api_type = str(self.get_config("api_type", "completions")).lower()
                extend_system_prompt = self.get_config("extend_selection_system_prompt", "")
                extend_max_tokens = self.get_config("extend_selection_max_tokens", 70)
                edit_system_prompt = self.get_config("edit_selection_system_prompt", "")
                edit_max_new_tokens = self.get_config("edit_selection_max_new_tokens", 0)
                try:
                    edit_max_new_tokens = int(edit_max_new_tokens)
                except (TypeError, ValueError):
                    edit_max_new_tokens = 0

                for row in row_range:
                    for col in col_range:
                        cell = sheet.getCellByPosition(col, row)

                        if args == "ExtendSelection":
                            cell_text = cell.getString()
                            if not cell_text:
                                continue
                            try:
                                def append_cell_text(chunk_text, target_cell=cell):
                                    target_cell.setString(target_cell.getString() + chunk_text)
                                self.stream_completion(cell_text, extend_system_prompt, extend_max_tokens, api_type, append_cell_text)
                            except Exception as e:
                                self.show_error(str(e), "LocalWriter: Extend Selection (Calc)")
                        elif args == "EditSelection":
                            cell_original = cell.getString()
                            try:
                                prompt = "ORIGINAL VERSION:\n" + cell_original + "\n Below is an edited version according to the following instructions. Don't waste time thinking, be as fast as you can. The edited text will be a shorter or longer version of the original text based on the instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                                max_tokens = len(cell_original) + edit_max_new_tokens

                                cell.setString("")

                                def append_edit_text(chunk_text, target_cell=cell):
                                    target_cell.setString(target_cell.getString() + chunk_text)

                                self.stream_completion(prompt, edit_system_prompt, max_tokens, api_type, append_edit_text)
                            except Exception as e:
                                cell.setString(cell_original)  # Restore original on failure
                                self.show_error(str(e), "LocalWriter: Edit Selection (Calc)")
            except Exception:
                pass
# Starting from Python IDE
def main():
    try:
        ctx = XSCRIPTCONTEXT
    except NameError:
        ctx = officehelper.bootstrap()
        if ctx is None:
            print("ERROR: Could not bootstrap default Office.")
            sys.exit(1)
    job = MainJob(ctx)
    job.trigger("hello")
# Starting from command line
if __name__ == "__main__":
    main()

# pythonloader loads a static g_ImplementationHelper variable
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    MainJob,  # UNO object class
    "org.extension.localwriter.Main",  # implementation name (customize for yourself)
    ("com.sun.star.task.Job",), )  # implemented services (only 1)
# vim: set shiftwidth=4 softtabstop=4 expandtab:
