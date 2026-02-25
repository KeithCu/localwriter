"""Auto-generated module manifest. DO NOT EDIT."""

VERSION = '1.5.1'

MODULES = [
    {
        "name": "main",
        "description": "LocalWriter global settings",
        "requires": [],
        "provides_services": [],
        "config": {
                "debug": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Debug Mode"
                }
        },
        "actions": [
                "about"
        ],
        "action_icons": {}
},
    {
        "name": "core",
        "description": "Core services (document, config, events, format)",
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
    {
        "name": "ai",
        "description": "Unified AI provider registry (model catalog, instance selection)",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "ai"
        ],
        "config": {
                "default_text_instance": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Default Text AI",
                        "public": True,
                        "options_provider": "plugin.modules.ai.service:get_text_instance_options"
                },
                "default_image_instance": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Default Image AI",
                        "public": True,
                        "options_provider": "plugin.modules.ai.service:get_image_instance_options"
                },
                "custom_models": {
                        "type": "string",
                        "default": "[]",
                        "widget": "list_detail",
                        "inline": True,
                        "label": "Custom Models",
                        "helper": "Close Options to save; model lists refresh on reopen",
                        "name_field": "display_name",
                        "item_fields": {
                                "id": {
                                        "type": "string",
                                        "label": "Model ID",
                                        "widget": "text",
                                        "default": ""
                                },
                                "display_name": {
                                        "type": "string",
                                        "label": "Display Name",
                                        "widget": "text",
                                        "default": ""
                                },
                                "capability": {
                                        "type": "string",
                                        "label": "Capabilities",
                                        "widget": "text",
                                        "default": "text",
                                        "helper": "Comma-separated: text, image, vision, tools"
                                },
                                "providers": {
                                        "type": "string",
                                        "label": "Providers",
                                        "widget": "text",
                                        "default": "",
                                        "helper": "Comma-separated: openai, openrouter, together, ollama (empty = all)"
                                },
                                "priority": {
                                        "type": "int",
                                        "label": "Priority",
                                        "widget": "number",
                                        "default": 5,
                                        "min": 0,
                                        "max": 10,
                                        "helper": "Higher = listed first in model dropdowns (0-10)"
                                }
                        }
                },
                "models_file": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "Models File (YAML)",
                        "helper": "Override or extend the built-in model catalog for all providers"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "writer",
        "description": "Writer document tools (outline, content, comments, styles, tables, tracking, images)",
        "requires": [
                "document",
                "config",
                "format",
                "ai"
        ],
        "provides_services": [],
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
        "name": "calc",
        "description": "Calc spreadsheet tools (cells, sheets, formulas, charts)",
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
    {
        "name": "draw",
        "description": "Draw/Impress tools (shapes, pages/slides)",
        "requires": [
                "document",
                "config",
                "ai"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "http",
        "description": "HTTP server for extension endpoints",
        "requires": [
                "config",
                "events"
        ],
        "provides_services": [
                "http_routes"
        ],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enable HTTP Server",
                        "public": True
                },
                "port": {
                        "type": "int",
                        "default": 8766,
                        "min": 1024,
                        "max": 65535,
                        "widget": "number",
                        "label": "Server Port",
                        "public": True
                },
                "host": {
                        "type": "string",
                        "default": "localhost",
                        "widget": "text",
                        "label": "Bind Address",
                        "public": True
                },
                "use_ssl": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable HTTPS",
                        "public": True
                },
                "ssl_cert": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "SSL Certificate",
                        "helper": "Optional. Leave empty to use auto-generated self-signed certificate.",
                        "file_filter": "PEM files (*.pem)|*.pem|All files (*.*)|*.*"
                },
                "ssl_key": {
                        "type": "string",
                        "default": "",
                        "widget": "file",
                        "label": "SSL Private Key",
                        "helper": "Optional. Leave empty to use auto-generated self-signed key.",
                        "file_filter": "PEM files (*.pem)|*.pem"
                }
        },
        "actions": [
                "toggle_server",
                "server_status"
        ],
        "action_icons": {
                "toggle_server": "running",
                "server_status": "stopped"
        }
},
    {
        "name": "mcp",
        "description": "MCP JSON-RPC server for external tool access",
        "requires": [
                "document",
                "config",
                "events",
                "http_routes"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": True,
                        "widget": "checkbox",
                        "label": "Enable MCP Protocol",
                        "public": True
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "chatbot",
        "description": "AI chat sidebar",
        "requires": [
                "document",
                "config",
                "events",
                "ai"
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
    {
        "name": "tunnel",
        "description": "Tunnel providers for exposing MCP externally",
        "requires": [
                "config",
                "events",
                "http_routes"
        ],
        "provides_services": [
                "tunnel_manager"
        ],
        "config": {
                "auto_start": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Auto Start Tunnel",
                        "public": True
                },
                "provider": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Tunnel Provider",
                        "options_provider": "plugin.modules.tunnel:get_provider_options"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "batch",
        "description": "Batch tool execution with variable chaining",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "writer.nav",
        "description": "Writer document navigation \u2014 bookmarks, heading tree, proximity",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [
                "writer_bookmarks",
                "writer_tree",
                "writer_proximity"
        ],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "writer.index",
        "description": "Full-text search with stemming for Writer documents",
        "requires": [
                "document",
                "config",
                "events",
                "writer_tree"
        ],
        "provides_services": [
                "writer_index"
        ],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.bore",
        "description": "Bore tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "server": {
                        "type": "string",
                        "default": "bore.pub",
                        "widget": "text",
                        "label": "Bore Server",
                        "helper": "The bore server address (default: bore.pub)"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.cloudflare",
        "description": "Cloudflare tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "tunnel_name": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Tunnel Name"
                },
                "public_url": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Public URL",
                        "helper": "The public URL assigned by Cloudflare"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.ngrok",
        "description": "Ngrok tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {
                "authtoken": {
                        "type": "string",
                        "default": "",
                        "widget": "password",
                        "label": "Auth Token",
                        "helper": "Your ngrok authentication token"
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "tunnel.tailscale",
        "description": "Tailscale Funnel tunnel provider",
        "requires": [
                "tunnel_manager"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "common",
        "description": "Common tools for all document types",
        "requires": [
                "document",
                "config",
                "events"
        ],
        "provides_services": [],
        "config": {},
        "actions": [],
        "action_icons": {}
},
    {
        "name": "ai.openai",
        "description": "OpenAI-compatible API backend (OpenAI, OpenRouter, LM Studio, etc.)",
        "requires": [
                "ai"
        ],
        "provides_services": [],
        "config": {
                "default_endpoint": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Default Endpoint",
                        "placeholder": "https://api.openai.com/v1",
                        "helper": "Fallback API endpoint when no instance is configured",
                        "public": True
                },
                "default_model": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Default Model",
                        "helper": "Select a model from the catalog",
                        "public": True,
                        "options_provider": "plugin.modules.ai_openai:get_model_options"
                },
                "temperature": {
                        "type": "float",
                        "default": 0.7,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "widget": "slider",
                        "label": "Temperature",
                        "helper": "Controls randomness: 0 = deterministic, 2 = very creative"
                },
                "max_tokens": {
                        "type": "int",
                        "default": 4096,
                        "min": 1,
                        "max": 128000,
                        "widget": "number",
                        "label": "Max Tokens",
                        "helper": "Maximum number of tokens in the generated response"
                },
                "request_timeout": {
                        "type": "int",
                        "default": 120,
                        "min": 10,
                        "max": 600,
                        "widget": "number",
                        "label": "Request Timeout (seconds)",
                        "helper": "Time limit for API calls before they are cancelled"
                },
                "instances": {
                        "type": "string",
                        "default": "[]",
                        "widget": "list_detail",
                        "inline": True,
                        "label": "Instances",
                        "name_field": "name",
                        "item_fields": {
                                "name": {
                                        "type": "string",
                                        "label": "Name",
                                        "widget": "text",
                                        "default": ""
                                },
                                "endpoint": {
                                        "type": "string",
                                        "label": "API Endpoint",
                                        "widget": "text",
                                        "default": ""
                                },
                                "api_key": {
                                        "type": "string",
                                        "label": "API Key",
                                        "widget": "password",
                                        "default": ""
                                },
                                "model": {
                                        "type": "string",
                                        "label": "Model",
                                        "widget": "select",
                                        "default": "",
                                        "options_from": "default_model"
                                },
                                "image": {
                                        "type": "boolean",
                                        "label": "Image Generation",
                                        "widget": "checkbox",
                                        "default": False,
                                        "helper": "Enable /v1/images/generations for this instance"
                                }
                        }
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "ai.ollama",
        "description": "Ollama local LLM backend",
        "requires": [
                "ai"
        ],
        "provides_services": [],
        "config": {
                "default_endpoint": {
                        "type": "string",
                        "default": "http://localhost:11434",
                        "widget": "text",
                        "label": "Default Ollama URL",
                        "helper": "Fallback URL when no instance is configured",
                        "public": True
                },
                "default_model": {
                        "type": "string",
                        "default": "",
                        "widget": "select",
                        "label": "Default Model",
                        "helper": "Select a model from the catalog",
                        "public": True,
                        "options_provider": "plugin.modules.ai_ollama:get_model_options"
                },
                "temperature": {
                        "type": "float",
                        "default": 0.7,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "widget": "slider",
                        "label": "Temperature",
                        "helper": "Controls randomness: 0 = deterministic, 2 = very creative"
                },
                "max_tokens": {
                        "type": "int",
                        "default": 4096,
                        "min": 1,
                        "max": 128000,
                        "widget": "number",
                        "label": "Max Tokens",
                        "helper": "Maximum number of tokens in the generated response"
                },
                "request_timeout": {
                        "type": "int",
                        "default": 300,
                        "min": 10,
                        "max": 600,
                        "widget": "number",
                        "label": "Request Timeout (seconds)",
                        "helper": "Ollama may need longer for initial model loading"
                },
                "instances": {
                        "type": "string",
                        "default": "[]",
                        "widget": "list_detail",
                        "inline": True,
                        "label": "Instances",
                        "name_field": "name",
                        "item_fields": {
                                "name": {
                                        "type": "string",
                                        "label": "Name",
                                        "widget": "text",
                                        "default": ""
                                },
                                "endpoint": {
                                        "type": "string",
                                        "label": "Ollama URL",
                                        "widget": "text",
                                        "default": "http://localhost:11434"
                                },
                                "model": {
                                        "type": "string",
                                        "label": "Model",
                                        "widget": "select",
                                        "default": "",
                                        "options_from": "default_model"
                                }
                        }
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "ai.horde",
        "description": "AI Horde image generation (free, no key required)",
        "requires": [
                "ai"
        ],
        "provides_services": [],
        "config": {
                "default_model": {
                        "type": "string",
                        "default": "stable_diffusion",
                        "widget": "select",
                        "label": "Default Model",
                        "helper": "Fallback model when no instance is configured",
                        "public": True,
                        "options_provider": "plugin.modules.ai_horde:get_model_options"
                },
                "max_wait": {
                        "type": "int",
                        "default": 5,
                        "min": 1,
                        "max": 30,
                        "widget": "number",
                        "label": "Max Wait (minutes)",
                        "helper": "Maximum time to wait for AI Horde to generate an image"
                },
                "nsfw": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Allow NSFW",
                        "helper": "Allow Not-Safe-For-Work content in generated images"
                },
                "instances": {
                        "type": "string",
                        "default": "[]",
                        "widget": "list_detail",
                        "inline": True,
                        "label": "Instances",
                        "name_field": "name",
                        "item_fields": {
                                "name": {
                                        "type": "string",
                                        "label": "Name",
                                        "widget": "text",
                                        "default": ""
                                },
                                "api_key": {
                                        "type": "string",
                                        "label": "API Key",
                                        "widget": "text",
                                        "default": "0000000000"
                                },
                                "model": {
                                        "type": "string",
                                        "label": "Model",
                                        "widget": "select",
                                        "default": "stable_diffusion",
                                        "options_from": "default_model"
                                }
                        }
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "chatbot_api",
        "description": "REST/SSE API for the chatbot (external clients)",
        "requires": [
                "config",
                "events",
                "http_routes",
                "ai",
                "document"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable Chat API",
                        "helper": "Expose /api/chat endpoints on the HTTP server",
                        "public": True
                },
                "auth_token": {
                        "type": "string",
                        "default": "",
                        "widget": "text",
                        "label": "Auth Token",
                        "helper": "Optional Bearer token. Leave empty to disable auth."
                }
        },
        "actions": [],
        "action_icons": {}
},
    {
        "name": "debug",
        "description": "Debug tools and diagnostics",
        "requires": [
                "config",
                "events",
                "ai",
                "document"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable Debug Actions",
                        "helper": "Debug actions appear in menus but only execute when enabled",
                        "public": True
                }
        },
        "actions": [
                "debug_info",
                "test_providers"
        ],
        "action_icons": {}
},
    {
        "name": "ai.dummy",
        "description": "Dummy AI provider for testing (Homer Simpson mode)",
        "requires": [
                "config",
                "ai"
        ],
        "provides_services": [],
        "config": {
                "enabled": {
                        "type": "boolean",
                        "default": False,
                        "widget": "checkbox",
                        "label": "Enable Dummy Provider",
                        "helper": "Registers a fake AI that responds like Homer Simpson",
                        "public": True
                },
                "delay": {
                        "type": "int",
                        "default": 50,
                        "min": 0,
                        "max": 2000,
                        "widget": "number",
                        "label": "Streaming Delay (ms)",
                        "helper": "Delay between streamed chunks in milliseconds"
                }
        },
        "actions": [],
        "action_icons": {}
},
]
