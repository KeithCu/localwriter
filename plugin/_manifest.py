"""Auto-generated module manifest. DO NOT EDIT."""

VERSION = '1.7.2'

MODULES = [
    {
        "name": "main",
        "title": "LocalWriter global settings",
        "requires": [],
        "provides_services": [],
        "config": {},
        "actions": [
                "about"
        ],
        "action_icons": {}
},
    {
        "name": "core",
        "title": "Core services (config, events, logging)",
        "requires": [],
        "provides_services": [
                "document",
                "config",
                "events",
                "format"
        ],
        "config": {
                "log_level": {
                        "type": "string",
                        "default": "WARN",
                        "widget": "select",
                        "label": "Log Level",
                        "public": True,
                        "options": [
                                {
                                        "value": "DEBUG",
                                        "label": "Debug"
                                },
                                {
                                        "value": "INFO",
                                        "label": "Info"
                                },
                                {
                                        "value": "WARN",
                                        "label": "Warning"
                                },
                                {
                                        "value": "ERROR",
                                        "label": "Error"
                                }
                        ]
                }
        },
        "actions": [],
        "action_icons": {}
},
#     {
#         "name": "ai",
#         "title": "AI provider registry and model catalog",
#         "requires": [
#                 "config",
#                 "events"
#         ],
#         "provides_services": [
#                 "ai"
#         ],
#         "config": {
#                 "default_text_instance": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "select",
#                         "label": "Default Text AI",
#                         "public": True,
#                         "options_provider": "plugin.modules.ai.service:get_text_instance_options"
#                 },
#                 "default_image_instance": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "select",
#                         "label": "Default Image AI",
#                         "public": True,
#                         "options_provider": "plugin.modules.ai.service:get_image_instance_options"
#                 },
#                 "custom_models": {
#                         "type": "string",
#                         "default": "[]",
#                         "widget": "list_detail",
#                         "inline": True,
#                         "label": "Custom Models",
#                         "helper": "Close Options to save; model lists refresh on reopen",
#                         "name_field": "display_name",
#                         "item_fields": {
#                                 "id": {
#                                         "type": "string",
#                                         "label": "Model ID",
#                                         "widget": "text",
#                                         "default": ""
#                                 },
#                                 "display_name": {
#                                         "type": "string",
#                                         "label": "Display Name",
#                                         "widget": "text",
#                                         "default": ""
#                                 },
#                                 "capability": {
#                                         "type": "string",
#                                         "label": "Capabilities",
#                                         "widget": "text",
#                                         "default": "text",
#                                         "helper": "Comma-separated: text, image, vision, tools"
#                                 },
#                                 "providers": {
#                                         "type": "string",
#                                         "label": "Providers",
#                                         "widget": "text",
#                                         "default": "",
#                                         "helper": "Comma-separated: openai, openrouter, together, ollama (empty = all)"
#                                 },
#                                 "priority": {
#                                         "type": "int",
#                                         "label": "Priority",
#                                         "widget": "number",
#                                         "default": 5,
#                                         "min": 0,
#                                         "max": 10,
#                                         "helper": "Higher = listed first in model dropdowns (0-10)"
#                                 }
#                         }
#                 },
#                 "models_file": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "file",
#                         "label": "Models File (YAML)",
#                         "helper": "Override or extend the built-in model catalog for all providers"
#                 },
#                 "openai_endpoint": {
#                         "type": "string",
#                         "default": "",
#                         "label": "OpenAI Default Endpoint",
#                         "placeholder": "https://api.openai.com/v1"
#                 },
#                 "openai_model": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "select",
#                         "label": "OpenAI Default Model",
#                         "options_provider": "plugin.modules.ai:get_openai_model_options"
#                 },
#                 "openai_instances": {
#                         "type": "string",
#                         "default": "[]",
#                         "widget": "list_detail",
#                         "inline": True,
#                         "label": "OpenAI Instances",
#                         "name_field": "name",
#                         "item_fields": {
#                                 "name": {
#                                         "type": "string",
#                                         "label": "Name"
#                                 },
#                                 "endpoint": {
#                                         "type": "string",
#                                         "label": "Endpoint"
#                                 },
#                                 "api_key": {
#                                         "type": "string",
#                                         "label": "API Key",
#                                         "widget": "password"
#                                 },
#                                 "model": {
#                                         "type": "string",
#                                         "label": "Model",
#                                         "widget": "select",
#                                         "options_from": "openai_model"
#                                 },
#                                 "image": {
#                                         "type": "boolean",
#                                         "label": "Images",
#                                         "widget": "checkbox"
#                                 }
#                         }
#                 },
#                 "ollama_endpoint": {
#                         "type": "string",
#                         "default": "http://localhost:11434",
#                         "label": "Ollama Default URL"
#                 },
#                 "ollama_model": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "select",
#                         "label": "Ollama Default Model",
#                         "options_provider": "plugin.modules.ai:get_ollama_model_options"
#                 },
#                 "ollama_instances": {
#                         "type": "string",
#                         "default": "[]",
#                         "widget": "list_detail",
#                         "inline": True,
#                         "label": "Ollama Instances",
#                         "name_field": "name",
#                         "item_fields": {
#                                 "name": {
#                                         "type": "string",
#                                         "label": "Name"
#                                 },
#                                 "endpoint": {
#                                         "type": "string",
#                                         "label": "URL",
#                                         "default": "http://localhost:11434"
#                                 },
#                                 "model": {
#                                         "type": "string",
#                                         "label": "Model",
#                                         "widget": "select",
#                                         "options_from": "ollama_model"
#                                 }
#                         }
#                 },
#                 "horde_api_key": {
#                         "type": "string",
#                         "default": "0000000000",
#                         "widget": "password",
#                         "label": "Horde API Key"
#                 },
#                 "horde_instances": {
#                         "type": "string",
#                         "default": "[]",
#                         "widget": "list_detail",
#                         "inline": True,
#                         "label": "Horde Instances",
#                         "name_field": "name",
#                         "item_fields": {
#                                 "name": {
#                                         "type": "string",
#                                         "label": "Name"
#                                 },
#                                 "api_key": {
#                                         "type": "string",
#                                         "label": "API Key",
#                                         "widget": "password"
#                                 },
#                                 "model": {
#                                         "type": "string",
#                                         "label": "Model"
#                                 }
#                         }
#                 },
#                 "ai_temperature": {
#                         "type": "float",
#                         "default": 0.7,
#                         "min": 0.0,
#                         "max": 2.0,
#                         "widget": "slider",
#                         "label": "Temperature"
#                 },
#                 "ai_max_tokens": {
#                         "type": "int",
#                         "default": 4096,
#                         "widget": "number",
#                         "label": "Max Tokens"
#                 }
#         },
#         "actions": [],
#         "action_icons": {}
# },
# 
#     {
#         "name": "doc",
#         "title": "Common tools and diagnostics",
#         "requires": [
#                 "document",
#                 "config",
#                 "events",
#                 "ai"
#         ],
#         "provides_services": [],
#         "config": {
#                 "debug_enabled": {
#                         "type": "boolean",
#                         "default": False,
#                         "widget": "checkbox",
#                         "label": "Enable Debug Actions",
#                         "helper": "Debug actions appear in menus but only execute when enabled",
#                         "public": True
#                 }
#         },
#         "actions": [
#                 "debug_info",
#                 "test_providers"
#         ],
#         "action_icons": {}
# },
# 
#     {
#         "name": "http",
#         "title": "Built-in HTTP server",
#         "requires": [
#                 "config",
#                 "events"
#         ],
#         "provides_services": [
#                 "http_routes"
#         ],
#         "config": {
#                 "enabled": {
#                         "type": "boolean",
#                         "default": True,
#                         "widget": "checkbox",
#                         "label": "Enable HTTP Server",
#                         "public": True
#                 },
#                 "port": {
#                         "type": "int",
#                         "default": 8766,
#                         "min": 1024,
#                         "max": 65535,
#                         "widget": "number",
#                         "label": "Server Port",
#                         "public": True
#                 },
#                 "host": {
#                         "type": "string",
#                         "default": "localhost",
#                         "widget": "text",
#                         "label": "Bind Address",
#                         "public": True
#                 },
#                 "use_ssl": {
#                         "type": "boolean",
#                         "default": False,
#                         "widget": "checkbox",
#                         "label": "Enable HTTPS",
#                         "public": True
#                 },
#                 "ssl_cert": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "file",
#                         "label": "SSL Certificate",
#                         "helper": "Optional. Leave empty to use auto-generated self-signed certificate.",
#                         "file_filter": "PEM files (*.pem)|*.pem|All files (*.*)|*.*"
#                 },
#                 "ssl_key": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "file",
#                         "label": "SSL Private Key",
#                         "helper": "Optional. Leave empty to use auto-generated self-signed key.",
#                         "file_filter": "PEM files (*.pem)|*.pem"
#                 },
#                 "mcp_enabled": {
#                         "type": "boolean",
#                         "default": True,
#                         "widget": "checkbox",
#                         "label": "Enable MCP Protocol",
#                         "public": True,
#                         "helper": "Expose MCP JSON-RPC routes on the same port"
#                 }
#         },
#         "actions": [
#                 "toggle_server",
#                 "server_status"
#         ],
#         "action_icons": {
#                 "toggle_server": "running",
#                 "server_status": "stopped"
#         }
# },
# 
#     {
#         "name": "draw",
#         "title": "Draw and Impress tools",
#         "requires": [
#                 "document",
#                 "config",
#                 "ai"
#         ],
#         "provides_services": [],
#         "config": {},
#         "actions": [],
#         "action_icons": {}
# },
# 
    {
        "name": "calc",
        "title": "Calc spreadsheet tools",
        "requires": [
                "document",
                "config"
        ],
        "provides_services": [],
        "config": {
                "max_rows_display": {
                        "type": "int",
                        "default": 1000,
                        "min": 100,
                        "max": 100000,
                        "widget": "number",
                        "label": "Max Rows Display",
                        "public": True
                }
        },
        "actions": [],
        "action_icons": {}
},
#     {
#         "name": "batch",
#         "title": "Batch tool execution with variable chaining",
#         "requires": [
#                 "document",
#                 "config",
#                 "events"
#         ],
#         "provides_services": [],
#         "config": {},
#         "actions": [],
#         "action_icons": {}
# },
# 
    {
        "name": "writer",
        "title": "Writer document tools (including navigation and search)",
        "requires": [
                "document",
                "config",
                "format",
                "ai",
                "events"
        ],
        "provides_services": [
                "writer_bookmarks",
                "writer_tree",
                "writer_proximity",
                "writer_index"
        ],
        "config": {
                "max_content_chars": {
                        "type": "int",
                        "default": 50000,
                        "min": 1000,
                        "max": 500000,
                        "widget": "number",
                        "label": "Max Content Size",
                        "public": True
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "chatbot",
        "title": "AI chat sidebar and REST API",
        "requires": [
                "document",
                "config",
                "events",
                "ai",
                "http_routes"
        ],
        "provides_services": [],
        "config": {
                "max_tool_rounds": {
                        "type": "int",
                        "default": 15,
                        "min": 1,
                        "max": 50,
                        "widget": "number",
                        "label": "Max Tool Rounds"
                },
                "context_strategy": {
                        "type": "string",
                        "default": "auto",
                        "widget": "select",
                        "label": "Document Context Strategy",
                        "helper": "How much document content to include in LLM context",
                        "options": [
                                {
                                        "value": "auto",
                                        "label": "Auto (by document size)"
                                },
                                {
                                        "value": "full",
                                        "label": "Full document text"
                                },
                                {
                                        "value": "page",
                                        "label": "Pages around cursor"
                                },
                                {
                                        "value": "tree",
                                        "label": "Outline + excerpt"
                                },
                                {
                                        "value": "stats",
                                        "label": "Stats + outline only"
                                }
                        ]
                },
                "system_prompt": {
                        "type": "string",
                        "default": "",
                        "widget": "textarea",
                        "label": "System Prompt"
                },
                "image_provider": {
                        "type": "string",
                        "default": "endpoint",
                        "widget": "select",
                        "label": "Image Provider",
                        "options": [
                                {
                                        "value": "endpoint",
                                        "label": "LLM Endpoint"
                                },
                                {
                                        "value": "ai_horde",
                                        "label": "AI Horde (free)"
                                }
                        ]
                },
                "extend_selection_max_tokens": {
                        "type": "int",
                        "default": 70,
                        "min": 10,
                        "max": 4096,
                        "widget": "number",
                        "label": "Extend Selection Max Tokens"
                },
                "edit_selection_max_new_tokens": {
                        "type": "int",
                        "default": 0,
                        "min": 0,
                        "max": 4096,
                        "widget": "number",
                        "label": "Edit Selection Extra Tokens",
                        "helper": "Extra tokens beyond original text length. 0 = same length as original."
                },
                "tool_broker": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Tool Broker",
                        "helper": "Two-tier tool delivery: LLM gets core tools first, activates others by intent"
                },
                "enter_sends": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enter Sends Message",
                        "helper": "Press Enter to send, Shift+Enter for newline"
                },
                "show_mcp_activity": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Show MCP Activity",
                        "public": True
                },
                "api_enabled": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable Chat API",
                        "helper": "Expose /api/chat endpoints on the HTTP server",
                        "public": True
                },
                "api_auth_token": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "API Auth Token",
                        "helper": "Optional Bearer token for researchers/external apps. Empty = no auth."
                },
                "query_history": {
                        "type": "string",
                        "default": "[]",
                        "internal": True
                }
        },
        "actions": [
                "extend_selection",
                "edit_selection"
        ],
        "action_icons": {}
},
#     {
#         "name": "tunnel",
#         "title": "Tunnel providers for external MCP access",
#         "requires": [
#                 "config",
#                 "events",
#                 "http_routes"
#         ],
#         "provides_services": [
#                 "tunnel_manager"
#         ],
#         "config": {
#                 "auto_start": {
#                         "type": "boolean",
#                         "default": False,
#                         "widget": "checkbox",
#                         "label": "Auto Start Tunnel",
#                         "public": True
#                 },
#                 "provider": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "select",
#                         "label": "Tunnel Provider",
#                         "options_provider": "plugin.modules.tunnel:get_provider_options"
#                 },
#                 "server": {
#                         "type": "string",
#                         "default": "bore.pub",
#                         "label": "Bore Server",
#                         "helper": "Relay server (default: bore.pub)"
#                 },
#                 "tunnel_name": {
#                         "type": "string",
#                         "default": "",
#                         "label": "Cloudflare Tunnel Name",
#                         "helper": "Optional: use a named tunnel instead of a quick tunnel"
#                 },
#                 "public_url": {
#                         "type": "string",
#                         "default": "",
#                         "label": "Cloudflare Public URL",
#                         "helper": "Required for named tunnels"
#                 },
#                 "authtoken": {
#                         "type": "string",
#                         "default": "",
#                         "widget": "password",
#                         "label": "Ngrok Authtoken"
#                 }
#         },
#         "actions": [],
#         "action_icons": {}
# },
# 
]
