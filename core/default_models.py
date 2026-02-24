"""Default models for various providers."""

DEFAULT_MODELS = {
    "openrouter": {
        "text": [
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "display_name": "Llama 3.3 70B Instruct",
                "context_length": 128000,
                "notes": "Versatile open-weight generalist; excellent tool calling and reasoning for document edits/chat",
                "priority": 9
            },
            {
                "id": "mistralai/mistral-large-3",
                "display_name": "Mistral Large 3",
                "context_length": 256000,
                "notes": "Flagship for agentic workflows; strong multimodal and tool use for complex tasks",
                "priority": 9
            },
            {
                "id": "openai/gpt-oss-120b",
                "display_name": "GPT-OSS 120B",
                "context_length": 128000,
                "notes": "OpenAI's open-weight reasoning specialist; cost-effective for daily instruction following",
                "priority": 8
            },
            {
                "id": "ibm/granite-4.0-8b-instruct",
                "display_name": "Granite 4.0 8B Instruct",
                "context_length": 128000,
                "notes": "Efficient enterprise model; improved tool calling for spreadsheets and edits",
                "priority": 7
            }
        ],
        "image": [
            {
                "id": "google/gemini-3.1-pro-preview",
                "display_name": "Gemini 3.1 Pro Preview",
                "context_length": 1000000,
                "notes": "Top vision/reasoning; high value for image analysis in documents",
                "priority": 9
            },
            {
                "id": "mistralai/pixtral-large",
                "display_name": "Pixtral Large",
                "context_length": 128000,
                "notes": "Open-weight multimodal; efficient for generation and editing",
                "priority": 8
            }
        ]
    },

    "together": {
        "text": [
            {
                "id": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "display_name": "Llama 3.3 70B Turbo",
                "context_length": 128000,
                "notes": "Fast, quantized for everyday tool use; great value at low inference cost",
                "priority": 9
            },
            {
                "id": "mistralai/Mistral-Large-3",
                "display_name": "Mistral Large 3",
                "context_length": 256000,
                "notes": "Agentic specialist; optimized for productivity tasks like code/editing",
                "priority": 9
            },
            {
                "id": "ibm/granite-4.0-8b-instruct",
                "display_name": "Granite 4.0 8B Instruct",
                "context_length": 128000,
                "notes": "Cost-effective reasoning; tuned for enterprise docs/spreadsheets",
                "priority": 7
            }
        ],
        "image": [
            {
                "id": "mistralai/Pixtral-Large",
                "display_name": "Pixtral Large",
                "context_length": 128000,
                "notes": "Efficient image understanding/generation; integrates with text workflows",
                "priority": 8
            }
        ]
    },

    "ollama": {
        "text": [
            {
                "id": "llama3.3:8b-instruct",
                "display_name": "Llama 3.3 8B Instruct (local)",
                "context_length": 128000,
                "notes": "Efficient generalist; good for local chat/edits without huge VRAM needs",
                "priority": 9
            },
            {
                "id": "mistral:7b-instruct-v0.3",
                "display_name": "Mistral 7B Instruct v0.3 (local)",
                "context_length": 32768,
                "notes": "Fast inference; reliable for function calling and daily tasks",
                "priority": 8
            },
            {
                "id": "granite4.0:8b",
                "display_name": "Granite 4.0 8B (local)",
                "context_length": 128000,
                "notes": "Enterprise-tuned; strong tool improvements for spreadsheets",
                "priority": 7
            },
            {
                "id": "gemma3:9b-instruct",
                "display_name": "Gemma 3 9B Instruct (local)",
                "context_length": 8192,
                "notes": "Compact and efficient; excellent for instruction following on modest hardware",
                "priority": 7
            }
        ],
        "image": []  # As requested, no image models for Ollama
    },

    "mistral": {
        "text": [
            {
                "id": "mistral-large-3",
                "display_name": "Mistral Large 3",
                "context_length": 256000,
                "notes": "Flagship open-weight; top for agentic/tool use in docs",
                "priority": 10
            },
            {
                "id": "devstral-2",
                "display_name": "Devstral 2",
                "context_length": 128000,
                "notes": "Coding/agent specialist; value for development workflows",
                "priority": 9
            },
            {
                "id": "ministral-14b-reasoning",
                "display_name": "Ministral 14B Reasoning",
                "context_length": 128000,
                "notes": "Efficient edge model; cost-effective for local reasoning",
                "priority": 8
            }
        ],
        "image": [
            {
                "id": "pixtral-large",
                "display_name": "Pixtral Large",
                "context_length": 128000,
                "notes": "Strong vision + text; ideal for image features in LocalWriter",
                "priority": 9
            }
        ]
    },

    "groq": {
        "text": [
            {
                "id": "llama-3.3-70b-versatile",
                "display_name": "Llama 3.3 70B",
                "context_length": 128000,
                "notes": "Ultra-fast open-weight; best value for quick edits/chat",
                "priority": 9
            },
            {
                "id": "deepseek-r1-distill-70b",
                "display_name": "DeepSeek R1 Distill 70B",
                "context_length": 128000,
                "notes": "Fast reasoning; efficient for daily tool-calling (limited Chinese pick)",
                "priority": 8
            },
            {
                "id": "mixtral-8x22b-32768",
                "display_name": "Mixtral 8x22B",
                "context_length": 32768,
                "notes": "Mixture-of-experts; cost-effective speed for agentic tasks",
                "priority": 7
            }
        ],
        "image": []  # No dedicated image models highlighted; focus on text speed
    }
}