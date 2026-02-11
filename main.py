import sys
import unohelper
import officehelper
import json
import urllib.request
import urllib.parse
import ssl
from com.sun.star.task import XJobExecutor
from com.sun.star.awt import MessageBoxButtons as MSG_BUTTONS
import uno
import os 
import logging
import re

from com.sun.star.beans import PropertyValue
from com.sun.star.container import XNamed


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
                'temperature': 1,
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
                'temperature': 1,
                'top_p': 0.9,
                'stream': True
            }
            if not self._is_openai_compatible():
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
        
        try:
            with urllib.request.urlopen(request, context=ssl_context) as response:
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
                        append_callback(str(e))
                        toolkit.processEventsToIdle()
        except Exception as e:
            log_to_file(f"ERROR in stream_request: {str(e)}")
            append_callback(f"ERROR: {str(e)}")
            toolkit.processEventsToIdle()

    #retrieved from https://wiki.documentfoundation.org/Macros/General/IO_to_Screen
    #License: Creative Commons Attribution-ShareAlike 3.0 Unported License,
    #License: The Document Foundation  https://creativecommons.org/licenses/by-sa/3.0/
    #begin sharealike section 
    def input_box(self,message, title="", default="", x=None, y=None):
        """ Shows dialog with input box.
            @param message message to show on the dialog
            @param title window title
            @param default default value
            @param x optional dialog position in twips
            @param y optional dialog position in twips
            @return string if OK button pushed, otherwise zero length string
        """
        WIDTH = 600
        HORI_MARGIN = VERT_MARGIN = 8
        BUTTON_WIDTH = 100
        BUTTON_HEIGHT = 26
        HORI_SEP = VERT_SEP = 8
        LABEL_HEIGHT = BUTTON_HEIGHT * 2 + 5
        EDIT_HEIGHT = 24
        HEIGHT = VERT_MARGIN * 2 + LABEL_HEIGHT + VERT_SEP + EDIT_HEIGHT
        import uno
        from com.sun.star.awt.PosSize import POS, SIZE, POSSIZE
        from com.sun.star.awt.PushButtonType import OK, CANCEL
        from com.sun.star.util.MeasureUnit import TWIP
        ctx = uno.getComponentContext()
        def create(name):
            return ctx.getServiceManager().createInstanceWithContext(name, ctx)
        dialog = create("com.sun.star.awt.UnoControlDialog")
        dialog_model = create("com.sun.star.awt.UnoControlDialogModel")
        dialog.setModel(dialog_model)
        dialog.setVisible(False)
        dialog.setTitle(title)
        dialog.setPosSize(0, 0, WIDTH, HEIGHT, SIZE)
        def add(name, type, x_, y_, width_, height_, props):
            model = dialog_model.createInstance("com.sun.star.awt.UnoControl" + type + "Model")
            dialog_model.insertByName(name, model)
            control = dialog.getControl(name)
            control.setPosSize(x_, y_, width_, height_, POSSIZE)
            for key, value in props.items():
                setattr(model, key, value)
        label_width = WIDTH - BUTTON_WIDTH - HORI_SEP - HORI_MARGIN * 2
        add("label", "FixedText", HORI_MARGIN, VERT_MARGIN, label_width, LABEL_HEIGHT, 
            {"Label": str(message), "NoLabel": True})
        add("btn_ok", "Button", HORI_MARGIN + label_width + HORI_SEP, VERT_MARGIN, 
                BUTTON_WIDTH, BUTTON_HEIGHT, {"PushButtonType": OK, "DefaultButton": True})
        add("edit", "Edit", HORI_MARGIN, LABEL_HEIGHT + VERT_MARGIN + VERT_SEP, 
                WIDTH - HORI_MARGIN * 2, EDIT_HEIGHT, {"Text": str(default)})
        frame = create("com.sun.star.frame.Desktop").getCurrentFrame()
        window = frame.getContainerWindow() if frame else None
        dialog.createPeer(create("com.sun.star.awt.Toolkit"), window)
        if not x is None and not y is None:
            ps = dialog.convertSizeToPixel(uno.createUnoStruct("com.sun.star.awt.Size", x, y), TWIP)
            _x, _y = ps.Width, ps.Height
        elif window:
            ps = window.getPosSize()
            _x = ps.Width / 2 - WIDTH / 2
            _y = ps.Height / 2 - HEIGHT / 2
        dialog.setPosSize(_x, _y, 0, 0, POS)
        edit = dialog.getControl("edit")
        edit.setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(str(default))))
        edit.setFocus()
        ret = edit.getModel().Text if dialog.execute() else ""
        dialog.dispose()
        return ret

    def settings_box(self,title="", x=None, y=None):
        """ Settings dialog with configurable backend options """
        WIDTH = 600
        HORI_MARGIN = VERT_MARGIN = 8
        BUTTON_WIDTH = 100
        BUTTON_HEIGHT = 26
        HORI_SEP = 8
        VERT_SEP = 4
        LABEL_HEIGHT = BUTTON_HEIGHT  + 5
        EDIT_HEIGHT = 24
        import uno
        from com.sun.star.awt.PosSize import POS, SIZE, POSSIZE
        from com.sun.star.awt.PushButtonType import OK, CANCEL
        from com.sun.star.util.MeasureUnit import TWIP
        ctx = uno.getComponentContext()
        def create(name):
            return ctx.getServiceManager().createInstanceWithContext(name, ctx)
        dialog = create("com.sun.star.awt.UnoControlDialog")
        dialog_model = create("com.sun.star.awt.UnoControlDialogModel")
        dialog.setModel(dialog_model)
        dialog.setVisible(False)
        dialog.setTitle(title)

        openai_compatibility_value = "true" if self._as_bool(self.get_config("openai_compatibility", False)) else "false"
        is_openwebui_value = "true" if self._as_bool(self.get_config("is_openwebui", False)) else "false"
        field_specs = [
            {"name": "endpoint", "label": "Endpoint URL/Port:", "value": str(self.get_config("endpoint","http://127.0.0.1:5000"))},
            {"name": "model", "label": "Model (Required by Ollama/OpenAI):", "value": str(self.get_config("model",""))},
            {"name": "api_key", "label": "API Key (for OpenAI-compatible endpoints):", "value": str(self.get_config("api_key",""))},
            {"name": "api_type", "label": "API Type (completions/chat):", "value": str(self.get_config("api_type","completions"))},
            {"name": "is_openwebui", "label": "Is OpenWebUI endpoint? (true/false):", "value": is_openwebui_value, "type": "bool"},
            {"name": "openai_compatibility", "label": "OpenAI Compatible Endpoint? (true/false):", "value": openai_compatibility_value, "type": "bool"},
            {"name": "extend_selection_max_tokens", "label": "Extend Selection Max Tokens:", "value": str(self.get_config("extend_selection_max_tokens","70")), "type": "int"},
            {"name": "extend_selection_system_prompt", "label": "Extend Selection System Prompt:", "value": str(self.get_config("extend_selection_system_prompt",""))},
            {"name": "edit_selection_max_new_tokens", "label": "Edit Selection Max New Tokens:", "value": str(self.get_config("edit_selection_max_new_tokens","0")), "type": "int"},
            {"name": "edit_selection_system_prompt", "label": "Edit Selection System Prompt:", "value": str(self.get_config("edit_selection_system_prompt",""))},
        ]

        num_fields = len(field_specs)
        total_field_height = num_fields * (LABEL_HEIGHT + EDIT_HEIGHT + 2 * VERT_SEP)
        HEIGHT = VERT_MARGIN * 2 + total_field_height
        dialog.setPosSize(0, 0, WIDTH, HEIGHT, SIZE)

        def add(name, type, x_, y_, width_, height_, props):
            model = dialog_model.createInstance("com.sun.star.awt.UnoControl" + type + "Model")
            dialog_model.insertByName(name, model)
            control = dialog.getControl(name)
            control.setPosSize(x_, y_, width_, height_, POSSIZE)
            for key, value in props.items():
                setattr(model, key, value)

        label_width = WIDTH - BUTTON_WIDTH - HORI_SEP - HORI_MARGIN * 2
        field_controls = {}
        current_y = VERT_MARGIN
        for idx, field in enumerate(field_specs):
            label_name = f"label_{field['name']}"
            edit_name = f"edit_{field['name']}"
            add(label_name, "FixedText", HORI_MARGIN, current_y, label_width, LABEL_HEIGHT,
                {"Label": field["label"], "NoLabel": True})
            if idx == 0:
                add("btn_ok", "Button", HORI_MARGIN + label_width + HORI_SEP, current_y,
                    BUTTON_WIDTH, BUTTON_HEIGHT, {"PushButtonType": OK, "DefaultButton": True})
            current_y += LABEL_HEIGHT + VERT_SEP
            add(edit_name, "Edit", HORI_MARGIN, current_y,
                WIDTH - HORI_MARGIN * 2, EDIT_HEIGHT, {"Text": field["value"]})
            field_controls[field["name"]] = dialog.getControl(edit_name)
            current_y += EDIT_HEIGHT + VERT_SEP

        frame = create("com.sun.star.frame.Desktop").getCurrentFrame()
        window = frame.getContainerWindow() if frame else None
        dialog.createPeer(create("com.sun.star.awt.Toolkit"), window)
        if not x is None and not y is None:
            ps = dialog.convertSizeToPixel(uno.createUnoStruct("com.sun.star.awt.Size", x, y), TWIP)
            _x, _y = ps.Width, ps.Height
        elif window:
            ps = window.getPosSize()
            _x = ps.Width / 2 - WIDTH / 2
            _y = ps.Height / 2 - HEIGHT / 2
        dialog.setPosSize(_x, _y, 0, 0, POS)

        for field in field_specs:
            control = field_controls[field["name"]]
            text_value = str(field["value"])
            control.setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(text_value)))

        field_controls["endpoint"].setFocus()

        if dialog.execute():
            result = {}
            for field in field_specs:
                control_text = field_controls[field["name"]].getModel().Text
                field_type = field.get("type", "text")
                if field_type == "int":
                    if control_text.isdigit():
                        result[field["name"]] = int(control_text)
                elif field_type == "bool":
                    result[field["name"]] = self._as_bool(control_text)
                else:
                    result[field["name"]] = control_text
        else:
            result = {}

        dialog.dispose()
        return result
    #end sharealike section 

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
                        # Prepare request using the new unified method
                        system_prompt = self.get_config("extend_selection_system_prompt", "")
                        prompt = text_range.getString()
                        max_tokens = self.get_config("extend_selection_max_tokens", 70)
                        
                        api_type = str(self.get_config("api_type", "completions")).lower()
                        request = self.make_api_request(prompt, system_prompt, max_tokens, api_type=api_type)

                        def append_text(chunk_text):
                            text_range.setString(text_range.getString() + chunk_text)

                        self.stream_request(request, api_type, append_text)
                                      
                    except Exception as e:
                        text_range = selection.getByIndex(0)
                        # Append the user input to the selected text
                        text_range.setString(text_range.getString() + ": " + str(e))

            elif args == "EditSelection":
                # Access the current selection
                try:
                    user_input = self.input_box("Please enter edit instructions!", "Input", "")
                    
                    # Prepare the prompt for editing
                    prompt = "ORIGINAL VERSION:\n" + text_range.getString() + "\n Below is an edited version according to the following instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"
                    
                    system_prompt = self.get_config("edit_selection_system_prompt", "")
                    max_tokens = len(text_range.getString()) + self.get_config("edit_selection_max_new_tokens", 0)
                    
                    api_type = str(self.get_config("api_type", "completions")).lower()
                    request = self.make_api_request(prompt, system_prompt, max_tokens, api_type=api_type)
                    
                    text_range.setString("")

                    def append_text(chunk_text):
                        text_range.setString(text_range.getString() + chunk_text)

                    self.stream_request(request, api_type, append_text)

                except Exception as e:
                    text_range = selection.getByIndex(0)
                    # Append the user input to the selected text
                    text_range.setString(text_range.getString() + ": " + str(e))
            
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


                except Exception as e:
                    text_range = selection.getByIndex(0)
                    # Append the user input to the selected text
                    text_range.setString(text_range.getString() + ":error: " + str(e))
        elif hasattr(model, "Sheets"):
            try:
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
                    except Exception:
                        pass
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
                                request = self.make_api_request(cell_text, extend_system_prompt, extend_max_tokens, api_type=api_type)

                                def append_cell_text(chunk_text, target_cell=cell):
                                    target_cell.setString(target_cell.getString() + chunk_text)

                                self.stream_request(request, api_type, append_cell_text)
                            except Exception as e:
                                cell.setString(cell.getString() + ": " + str(e))
                        elif args == "EditSelection":
                            try:
                                prompt =  "ORIGINAL VERSION:\n" + cell.getString() + "\n Below is an edited version according to the following instructions. Don't waste time thinking, be as fast as you can. The edited text will be a shorter or longer version of the original text based on the instructions. There are no comments in the edited version. The edited version is followed by the end of the document. The original version will be edited as follows to create the edited version:\n" + user_input + "\nEDITED VERSION:\n"

                                max_tokens = len(cell.getString()) + edit_max_new_tokens
                                request = self.make_api_request(prompt, edit_system_prompt, max_tokens, api_type=api_type)

                                cell.setString("")

                                def append_edit_text(chunk_text, target_cell=cell):
                                    target_cell.setString(target_cell.getString() + chunk_text)

                                self.stream_request(request, api_type, append_edit_text)
                            except Exception as e:
                                cell.setString(cell.getString() + ": " + str(e))
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
    "org.extension.sample.do",  # implementation name (customize for yourself)
    ("com.sun.star.task.Job",), )  # implemented services (only 1)
# vim: set shiftwidth=4 softtabstop=4 expandtab:
