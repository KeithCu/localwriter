import sys
import os

# Ensure extension directory is on path so core.streaming_deltas can be imported
_ext_dir = os.path.dirname(os.path.abspath(__file__))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

import unohelper
import officehelper

from core.config import get_config, set_config, as_bool, get_api_config, populate_combobox_with_lru, update_lru_history
from core.api import LlmClient
from core.document import get_full_document_text, get_document_context_for_chat
from core.async_stream import run_stream_completion_async
from core.logging import log_to_file, agent_log
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

    def _populate_combobox_with_lru(self, ctrl, current_val, lru_key):
        """Delegate to core.config."""
        populate_combobox_with_lru(self.ctx, ctrl, current_val, lru_key)

    def _update_lru_history(self, val, lru_key, max_items=10):
        """Delegate to core.config."""
        update_lru_history(self.ctx, val, lru_key, max_items)

    def _apply_settings_result(self, result):
        """Apply settings dialog result to config. Shared by Writer and Calc."""
        # Define config keys that can be set directly
        direct_keys = [
            "extend_selection_max_tokens",
            "edit_selection_max_new_tokens",
            "api_key",
            "is_openwebui",
            "openai_compatibility",
            "model",
            "temperature",
            "seed",
            "chat_max_tokens",
            "chat_context_length",
            "additional_instructions",
            "request_timeout"
        ]
        
        # Set direct keys
        for key in direct_keys:
            if key in result:
                val = result[key]
                self.set_config(key, val)
                
                # Update LRU history
                if key == "model" and val:
                    self._update_lru_history(val, "model_lru")
                elif key == "additional_instructions" and val:
                    self._update_lru_history(val, "prompt_lru")

        
        # Handle special cases
        if "endpoint" in result and result["endpoint"].startswith("http"):
            self.set_config("endpoint", result["endpoint"])
        
        if "api_type" in result:
            api_type_value = str(result["api_type"]).strip().lower()
            if api_type_value not in ("chat", "completions"):
                api_type_value = "completions"
            self.set_config("api_type", api_type_value)


    def _get_client(self):
        """Create LlmClient with current config."""
        config = get_api_config(self.ctx)
        return LlmClient(config, self.ctx)

    def show_error(self, message, title="LocalWriter Error"):
        """Show an error message in a dialog instead of writing to the document."""
        desktop = self.sm.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        frame = desktop.getCurrentFrame()
        if frame and frame.ActiveFrame:
            frame = frame.ActiveFrame
        window_peer = frame.getContainerWindow() if frame else None
        if window_peer:
            toolkit = self.sm.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
            box = toolkit.createMessageBox(window_peer, ERRORBOX, BUTTONS_OK, title, str(message))
            box.execute()

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
        """ Shows input dialog (EditInputDialog.xdl). Returns (result_text, extra_prompt) if OK, else ("", ""). """
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
            
            # Populate prompt selector history
            prompt_ctrl = dlg.getControl("prompt_selector")
            current_prompt = self.get_config("additional_instructions", "")
            self._populate_combobox_with_lru(prompt_ctrl, current_prompt, "prompt_lru")

            dlg.getControl("edit").setFocus()
            dlg.getControl("edit").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(str(default))))
            
            if dlg.execute():
                ret_text = dlg.getControl("edit").getModel().Text
                ret_prompt = prompt_ctrl.getText()
                return ret_text, ret_prompt
            return "", ""
        finally:
            dlg.dispose()

    def settings_box(self, title="", x=None, y=None):
        """ Settings dialog loaded from XDL (LocalWriterDialogs/SettingsDialog.xdl).
        Uses DialogProvider for proper Map AppFont sizing. """
        """ Settings dialog loaded from XDL (LocalWriterDialogs/SettingsDialog.xdl).
        Uses DialogProvider for proper Map AppFont sizing. """
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
            {"name": "edit_selection_max_new_tokens", "value": str(self.get_config("edit_selection_max_new_tokens", "0")), "type": "int"},
            {"name": "chat_max_tokens", "value": str(self.get_config("chat_max_tokens", "16384")), "type": "int"},
            {"name": "chat_context_length", "value": str(self.get_config("chat_context_length", "8000")), "type": "int"},
            {"name": "additional_instructions", "value": str(self.get_config("additional_instructions", ""))},
            {"name": "request_timeout", "value": str(self.get_config("request_timeout", "120")), "type": "int"},
        ]

        pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        base_url = pip.getPackageLocation("org.extension.localwriter")
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dialog_url = base_url + "/LocalWriterDialogs/SettingsDialog.xdl"
        try:
            dlg = dp.createDialog(dialog_url)
        except BaseException:
            raise


        try:
            for field in field_specs:
                ctrl = dlg.getControl(field["name"])
                if ctrl:


                    if field["name"] == "model":
                        self._populate_combobox_with_lru(ctrl, field["value"], "model_lru")
                    elif field["name"] == "additional_instructions":
                        self._populate_combobox_with_lru(ctrl, field["value"], "prompt_lru")
                    else:
                        ctrl.getModel().Text = field["value"]
            dlg.getControl("endpoint").setFocus()

            try:
                exec_result = dlg.execute()

                result = {}
                if exec_result:
                    for field in field_specs:
                        try:
                            ctrl = dlg.getControl(field["name"])
                            if ctrl:
                                if field["name"] in ("model", "additional_instructions"):
                                    # For ComboBox, use getText() to get the actual edit text (user input)
                                    control_text = ctrl.getText()
                                else:
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
                                result[field["name"]] = ""
                        except Exception:
                            result[field["name"]] = ""
            except Exception:
                result = {}
                raise

        finally:
            dlg.dispose()
        return result

    def trigger(self, args):
        agent_log("main.py:trigger", "trigger called", data={"args": str(args)}, hypothesis_id="H1,H2")
        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)
        model = desktop.getCurrentComponent()
        agent_log("main.py:trigger", "model state", data={"model_is_none": model is None, "has_text": hasattr(model, "Text") if model else False, "has_sheets": hasattr(model, "Sheets") if model else False}, hypothesis_id="H2")
        #if not hasattr(model, "Text"):
        #    model = self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())

        if args == "settings" and (not model or (not hasattr(model, "Text") and not hasattr(model, "Sheets"))):
            agent_log("main.py:trigger", "settings requested but no Writer/Calc document", data={"args": str(args)}, hypothesis_id="H2")

        if args == "RunFormatTests":
            try:
                from core.format_tests import run_markdown_tests
                writer_model = model if (model and hasattr(model, "getText")) else None
                p, f, log = run_markdown_tests(self.ctx, writer_model)
                msg = "Format tests: %d passed, %d failed.\n\n%s" % (p, f, "\n".join(log))
                self.show_error(msg, "Format tests")
            except Exception as e:
                self.show_error("Tests failed to run: %s" % e, "Format tests")
            return

        if hasattr(model, "Text"):
            text = model.Text
            selection = model.CurrentController.getSelection()
            text_range = selection.getByIndex(0)

            
            if args == "ExtendSelection":
                # Access the current selection
                if len(text_range.getString()) > 0:
                    try:
                        extra_instructions = self.get_config("additional_instructions", "")
                        system_prompt = extra_instructions # Extend usually benefits from just the custom prompt or none
                        self._update_lru_history(system_prompt, "prompt_lru")
                        prompt = text_range.getString()
                        max_tokens = self.get_config("extend_selection_max_tokens", 70)
                        model_val = self.get_config("model", "")
                        self._update_lru_history(model_val, "model_lru")
                        api_type = str(self.get_config("api_type", "completions")).lower()
                        client = self._get_client()

                        def apply_chunk(chunk_text, is_thinking=False):
                            if not is_thinking:
                                text_range.setString(text_range.getString() + chunk_text)

                        run_stream_completion_async(
                            self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                            apply_chunk, lambda: None,
                            lambda e: self.show_error(str(e), "LocalWriter: Extend Selection"),
                        )
                    except Exception as e:
                        self.show_error(str(e), "LocalWriter: Extend Selection")

            elif args == "EditSelection":
                # Access the current selection
                original_text = text_range.getString()
                try:
                    user_input, extra_instructions = self.input_box("Please enter edit instructions!", "Input", "")
                    if not user_input:
                        return
                    
                    if extra_instructions:
                        self.set_config("additional_instructions", extra_instructions)
                        self._update_lru_history(extra_instructions, "prompt_lru")

                except Exception as e:
                    self.show_error(str(e), "LocalWriter: Edit Selection")
                    return
                prompt = "ORIGINAL VERSION:\n" + original_text + "\n Below is an edited version according to the following instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                system_prompt = extra_instructions or ""
                max_tokens = len(original_text) + self.get_config("edit_selection_max_new_tokens", 0)
                api_type = str(self.get_config("api_type", "completions")).lower()
                text_range.setString("")
                client = self._get_client()

                def apply_chunk(chunk_text, is_thinking=False):
                    if not is_thinking:
                        text_range.setString(text_range.getString() + chunk_text)

                def on_error(e):
                    text_range.setString(original_text)
                    self.show_error(str(e), "LocalWriter: Edit Selection")

                try:
                    run_stream_completion_async(
                        self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                        apply_chunk, lambda: None, on_error,
                    )
                except Exception as e:
                    text_range.setString(original_text)
                    self.show_error(str(e), "LocalWriter: Edit Selection")

            elif args == "ChatWithDocument":
                try:
                    max_context = int(self.get_config("chat_context_length", 8000))
                    doc_text = get_document_context_for_chat(model, max_context, include_end=True, include_selection=True)
                    if not doc_text.strip():
                        self.show_error("Document is empty.", "Chat with Document")
                        return
                    user_query, extra_instructions = self.input_box("Ask a question about your document:", "Chat with Document", "")
                    if not user_query:
                        return
                    
                    if extra_instructions:
                        self.set_config("additional_instructions", extra_instructions)
                        self._update_lru_history(extra_instructions, "prompt_lru")

                    prompt = f"Document content:\n\n{doc_text}\n\nUser question: {user_query}"
                    system_prompt = DEFAULT_CHAT_SYSTEM_PROMPT
                    if extra_instructions:
                        system_prompt += "\n\n" + str(extra_instructions)
                    max_tokens = int(self.get_config("chat_max_tokens", 512))
                    api_type = str(self.get_config("api_type", "completions")).lower()
                    text = model.Text
                    cursor = text.createTextCursor()
                    cursor.gotoEnd(False)
                    cursor.insertString("\n\n--- Chat response ---\n\n", False)
                    client = self._get_client()

                    def apply_chunk(chunk_text, is_thinking=False):
                        if chunk_text:
                            cursor.insertString(chunk_text, False)

                    run_stream_completion_async(
                        self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                        apply_chunk, lambda: None,
                        lambda e: self.show_error(str(e), "LocalWriter: Chat with Document"),
                    )
                except Exception as e:
                    self.show_error(str(e), "LocalWriter: Chat with Document")
            
            elif args == "settings":
                try:
                    agent_log("main.py:trigger", "about to call settings_box (Writer)", hypothesis_id="H1,H2")
                    result = self.settings_box("Settings")
                    self._apply_settings_result(result)
                except Exception as e:
                    agent_log("main.py:trigger", "settings exception (Writer)", data={"error": str(e)}, hypothesis_id="H5")
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
                        agent_log("main.py:trigger", "about to call settings_box (Calc)", hypothesis_id="H1,H2")
                        result = self.settings_box("Settings")
                        self._apply_settings_result(result)
                    except Exception as e:
                        agent_log("main.py:trigger", "settings exception (Calc)", data={"error": str(e)}, hypothesis_id="H5")
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

                # Build list of (cell, prompt, system_prompt, max_tokens, original_for_restore or None)
                tasks = []
                for row in row_range:
                    for col in col_range:
                        cell = sheet.getCellByPosition(col, row)
                        if args == "ExtendSelection":
                            cell_text = cell.getString()
                            if not cell_text:
                                continue
                            tasks.append((cell, cell_text, extend_system_prompt, extend_max_tokens, None))
                        elif args == "EditSelection":
                            cell_original = cell.getString()
                            prompt = "ORIGINAL VERSION:\n" + cell_original + "\n Below is an edited version according to the following instructions. Don't waste time thinking, be as fast as you can. The edited text will be a shorter or longer version of the original text based on the instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                            max_tokens = len(cell_original) + edit_max_new_tokens
                            tasks.append((cell, prompt, edit_system_prompt, max_tokens, cell_original))

                client = self._get_client()
                task_index = [0]

                def run_next_cell():
                    if task_index[0] >= len(tasks):
                        return
                    cell, prompt, system_prompt, max_tokens, original = tasks[task_index[0]]
                    task_index[0] += 1
                    if args == "EditSelection" and original is not None:
                        cell.setString("")

                    def apply_chunk(chunk_text, is_thinking=False):
                        if not is_thinking:
                            cell.setString(cell.getString() + chunk_text)

                    def on_done():
                        run_next_cell()

                    def on_error(e):
                        if original is not None:
                            cell.setString(original)
                        self.show_error(str(e), "LocalWriter: Edit Selection (Calc)" if args == "EditSelection" else "LocalWriter: Extend Selection (Calc)")
                        # Stop on first error: do not call run_next_cell()

                    run_stream_completion_async(
                        self.ctx, client, prompt, system_prompt, max_tokens, api_type,
                        apply_chunk, on_done, on_error,
                    )

                if tasks:
                    run_next_cell()
            except Exception as e:
                self.show_error(str(e), "LocalWriter: Calc Processing")
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
