import sys
import unohelper
import officehelper
import json
import urllib.request
import urllib.parse
import ssl
from com.sun.star.task import XJobExecutor
from com.sun.star.awt import MessageBoxButtons as MSG_BUTTONS
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK
import uno
import os 
import logging
import re

from com.sun.star.beans import PropertyValue
from com.sun.star.container import XNamed

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/114.0.0.0 Safari/537.36'
)

def log_to_file(message):
    # Get the user's home directory
    home_directory = os.path.expanduser('~')
    
    # Define the log file path
    log_file_path = os.path.join(home_directory, 'log.txt')
    
    # Set up logging configuration
    logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(message)s')
    
    # Log the input message
    logging.info(message)


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
    

    def get_config(self,key,default):
  
        name_file ="localwriter.json"
        #path_settings = create_instance('com.sun.star.util.PathSettings')
        
        
        path_settings = self.sm.createInstanceWithContext('com.sun.star.util.PathSettings', self.ctx)

        user_config_path = getattr(path_settings, "UserConfig")

        if user_config_path.startswith('file://'):
            user_config_path = str(uno.fileUrlToSystemPath(user_config_path))
        
        # Ensure the path ends with the filename
        config_file_path = os.path.join(user_config_path, name_file)

        # Check if the file exists
        if not os.path.exists(config_file_path):
            return default

        # Try to load the JSON content from the file
        try:
            with open(config_file_path, 'r') as file:
                config_data = json.load(file)
        except (IOError, json.JSONDecodeError):
            return default

        # Return the value corresponding to the key, or the default value if the key is not found
        return config_data.get(key, default)

    def set_config(self, key, value):
        name_file = "localwriter.json"
        
        path_settings = self.sm.createInstanceWithContext('com.sun.star.util.PathSettings', self.ctx)
        user_config_path = getattr(path_settings, "UserConfig")

        if user_config_path.startswith('file://'):
            user_config_path = str(uno.fileUrlToSystemPath(user_config_path))

        # Ensure the path ends with the filename
        config_file_path = os.path.join(user_config_path, name_file)

        # Load existing configuration if the file exists
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, 'r') as file:
                    config_data = json.load(file)
            except (IOError, json.JSONDecodeError):
                config_data = {}
        else:
            config_data = {}

        # Update the configuration with the new key-value pair
        config_data[key] = value

        # Write the updated configuration back to the file
        try:
            with open(config_file_path, 'w') as file:
                json.dump(config_data, file, indent=4)
        except IOError as e:
            # Handle potential IO errors (optional)
            print(f"Error writing to {config_file_path}: {e}")

    def _as_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(value, (int, float)):
            return value != 0
        return False

    def _is_openai_compatible(self):
        endpoint = str(self.get_config("endpoint", "http://127.0.0.1:5000"))
        compatibility_flag = self._as_bool(self.get_config("openai_compatibility", False))
        return compatibility_flag or ("api.openai.com" in endpoint.lower())

    def make_api_request(self, prompt, system_prompt="", max_tokens=70, api_type=None):
        """
        Build a streaming completion/chat request that can target local or OpenAI-compatible endpoints.
        """
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 70

        endpoint = str(self.get_config("endpoint", "http://127.0.0.1:5000")).rstrip("/")
        api_key = str(self.get_config("api_key", ""))
        if api_type is None:
            api_type = str(self.get_config("api_type", "completions")).lower()
        api_type = "chat" if api_type == "chat" else "completions"
        model = str(self.get_config("model", ""))
        
        log_to_file(f"=== API Request Debug ===")
        log_to_file(f"Endpoint: {endpoint}")
        log_to_file(f"API Type: {api_type}")
        log_to_file(f"Model: {model}")
        log_to_file(f"Max Tokens: {max_tokens}")

        headers = {
            'Content-Type': 'application/json'
        }

        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        # Detect OpenWebUI endpoints (they use /api/ instead of /v1/)
        is_openwebui = self._as_bool(self.get_config("is_openwebui", False)) or "open-webui" in endpoint.lower() or "openwebui" in endpoint.lower()
        api_path = "/api" if is_openwebui else "/v1"
        
        log_to_file(f"Is OpenWebUI: {is_openwebui}")
        log_to_file(f"API Path: {api_path}")

        temperature = self.get_config("temperature", 0.5)
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = 0.5
        seed_val = self.get_config("seed", "")

        if api_type == "chat":
            url = endpoint + api_path + "/chat/completions"
            log_to_file(f"Full URL: {url}")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            data = {
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': 0.9,
                'stream': True
            }
        else:
            url = endpoint + api_path + "/completions"
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"SYSTEM PROMPT\n{system_prompt}\nEND SYSTEM PROMPT\n{prompt}"
            data = {
                'prompt': full_prompt,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': 0.9,
                'stream': True
            }
            if not self._is_openai_compatible() or seed_val:
                try:
                    data['seed'] = int(seed_val) if seed_val else 10
                except (TypeError, ValueError):
                    data['seed'] = 10

        if model:
            data["model"] = model

        json_data = json.dumps(data).encode('utf-8')
        log_to_file(f"Request data: {json.dumps(data, indent=2)}")
        log_to_file(f"Headers: {headers}")
        
        # Note: method='POST' is implicit when data is provided
        request = urllib.request.Request(url, data=json_data, headers=headers)
        request.get_method = lambda: 'POST'
        return request

    def extract_content_from_response(self, chunk, api_type="completions"):
        """
        Extract text content from API response chunk based on API type.
        """
        if api_type == "chat":
            # OpenAI chat completions format
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                return delta.get("content", ""), chunk["choices"][0].get("finish_reason")
        else:
            # Legacy completions format
            if "choices" in chunk and len(chunk["choices"]) > 0:
                return chunk["choices"][0].get("text", ""), chunk["choices"][0].get("finish_reason")
        
        return "", None

    def get_ssl_context(self):
        """
        Create an SSL context that doesn't verify certificates.
        This is needed for some environments where SSL certificates are not properly configured.
        """
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _get_request_timeout(self):
        """Get request timeout in seconds from config (default 120)."""
        try:
            return int(self.get_config("request_timeout", 120))
        except (TypeError, ValueError):
            return 120

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

    def stream_completion(self, prompt, system_prompt, max_tokens, api_type, append_callback):
        """Single entry point for streaming completions. Raises on error."""
        request = self.make_api_request(prompt, system_prompt, max_tokens, api_type=api_type)
        self.stream_request(request, api_type, append_callback)

    def get_full_document_text(self, model, max_chars=8000):
        """Get full document text for Writer, truncated to max_chars."""
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            full = cursor.getString()
            if len(full) > max_chars:
                full = full[:max_chars] + "\n\n[... document truncated ...]"
            return full
        except Exception:
            return ""

    def stream_request(self, request, api_type, append_callback):
        """
        Stream a completion/chat response and append incremental chunks via the provided callback.
        """
        toolkit = self.ctx.getServiceManager().createInstanceWithContext(
            "com.sun.star.awt.Toolkit", self.ctx
        )
        ssl_context = self.get_ssl_context()
        
        log_to_file(f"=== Starting stream request ===")
        log_to_file(f"Request URL: {request.full_url}")
        log_to_file(f"Request method: {request.get_method()}")
        
        timeout = self._get_request_timeout()
        try:
            with urllib.request.urlopen(request, context=ssl_context, timeout=timeout) as response:
                log_to_file(f"Response status: {response.status}")
                log_to_file(f"Response headers: {response.headers}")
                
                for line in response:
                    try:
                        if line.strip() and line.startswith(b"data: "):
                            payload = line[len(b"data: "):].decode("utf-8").strip()
                            if payload == "[DONE]":
                                break
                            chunk = json.loads(payload)
                            content, finish_reason = self.extract_content_from_response(chunk, api_type)
                            if content:
                                append_callback(content)
                                toolkit.processEventsToIdle()
                            if finish_reason:
                                break
                    except Exception as e:
                        log_to_file(f"Error processing line: {str(e)}")
                        raise
        except Exception as e:
            log_to_file(f"ERROR in stream_request: {str(e)}")
            raise

    def input_box(self, message, title="", default="", x=None, y=None):
        """ Shows input dialog (EditInputDialog.xdl). Returns edit text if OK, else "". """
        import uno
        ctx = uno.getComponentContext()
        smgr = ctx.getServiceManager()
        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dlg = dp.createDialog("vnd.sun.star.script:LocalWriterDialogs.EditInputDialog?location=application")
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
        import uno
        ctx = uno.getComponentContext()
        smgr = ctx.getServiceManager()

        openai_compatibility_value = "true" if self._as_bool(self.get_config("openai_compatibility", False)) else "false"
        is_openwebui_value = "true" if self._as_bool(self.get_config("is_openwebui", False)) else "false"
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
        ]

        dp = smgr.createInstanceWithContext("com.sun.star.awt.DialogProvider", ctx)
        dlg = dp.createDialog("vnd.sun.star.script:LocalWriterDialogs.SettingsDialog?location=application")
        try:
            for field in field_specs:
                ctrl = dlg.getControl(field["name"])
                if ctrl:
                    ctrl.getModel().Text = field["value"]
            dlg.getControl("endpoint").setFocus()
            if dlg.execute():
                result = {}
                for field in field_specs:
                    ctrl = dlg.getControl(field["name"])
                    control_text = ctrl.getModel().Text if ctrl else ""
                    field_type = field.get("type", "text")
                    if field_type == "int":
                        result[field["name"]] = int(control_text) if control_text.isdigit() else control_text
                    elif field_type == "bool":
                        result[field["name"]] = self._as_bool(control_text)
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
        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx)
        model = desktop.getCurrentComponent()
        #if not hasattr(model, "Text"):
        #    model = self.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())

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
                    system_prompt = self.get_config("chat_system_prompt", "You are a helpful assistant. Answer the user's question based on the document content provided.")
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


                except Exception as e:
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
                    except Exception as e:
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
