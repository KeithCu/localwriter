"""PROMPT() Calc cell function — LLM-powered spreadsheet AddIn.

Provides =PROMPT(message, [system_prompt], [model], [max_tokens])
as a Calc cell function. Uses the framework's LLM service.

Registered as a UNO component in META-INF/manifest.xml.
Requires XPromptFunction.rdb for the interface definition.
"""

import logging
import os
import sys

log = logging.getLogger("localwriter.prompt_function")

# Ensure plugin parent on path
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_plugin_dir)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    import uno
    import unohelper
    from org.extension.localwriter.PromptFunction import XPromptFunction

    class PromptFunction(unohelper.Base, XPromptFunction):

        def __init__(self, ctx):
            self.ctx = ctx
            self._provider = None

        def _get_provider(self):
            """Lazily get the LLM provider via the framework."""
            if self._provider is not None:
                return self._provider
            try:
                from plugin.main import bootstrap, get_services
                bootstrap(self.ctx)
                services = get_services()
                self._provider = services.ai.get_provider("text")
            except Exception:
                log.exception("Failed to get LLM provider")
            return self._provider

        # ── XPromptFunction interface ─────────────────────────────

        def getProgrammaticFunctionName(self, aDisplayName):
            if aDisplayName == "PROMPT":
                return "prompt"
            return ""

        def getDisplayFunctionName(self, aProgrammaticName):
            if aProgrammaticName == "prompt":
                return "PROMPT"
            return ""

        def getFunctionDescription(self, aProgrammaticName):
            if aProgrammaticName == "prompt":
                return "Generates text using an LLM."
            return ""

        def getArgumentDescription(self, aProgrammaticName, nArgument):
            if aProgrammaticName == "prompt":
                descs = [
                    "The prompt to send to the LLM.",
                    "The system prompt to use.",
                    "The model to use.",
                    "The maximum number of tokens to generate.",
                ]
                if 0 <= nArgument < len(descs):
                    return descs[nArgument]
            return ""

        def getArgumentName(self, aProgrammaticName, nArgument):
            if aProgrammaticName == "prompt":
                names = ["message", "system_prompt", "model", "max_tokens"]
                if 0 <= nArgument < len(names):
                    return names[nArgument]
            return ""

        def hasFunctionWizard(self, aProgrammaticName):
            return True

        def getArgumentCount(self, aProgrammaticName):
            if aProgrammaticName == "prompt":
                return 4
            return 0

        def getArgumentIsOptional(self, aProgrammaticName, nArgument):
            if aProgrammaticName == "prompt":
                return nArgument > 0
            return False

        def getProgrammaticCategoryName(self, aProgrammaticName):
            return "Add-In"

        def getDisplayCategoryName(self, aProgrammaticName):
            return "Add-In"

        def getLocale(self):
            return self.ctx.ServiceManager.createInstance(
                "com.sun.star.lang.Locale", ("en", "US", ""))

        def setLocale(self, locale):
            pass

        def load(self, xSomething):
            pass

        def unload(self):
            pass

        # ── The actual PROMPT function ────────────────────────────

        def prompt(self, message, systemPrompt, model, maxTokens):
            try:
                provider = self._get_provider()
                if provider is None:
                    return "[Error: No LLM provider configured]"

                system_prompt = systemPrompt or ""
                max_tokens = 70
                if maxTokens is not None:
                    try:
                        max_tokens = int(maxTokens)
                    except (TypeError, ValueError):
                        pass

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": str(message)})

                result = provider.complete(
                    messages, max_tokens=max_tokens)
                return result.get("content") or ""

            except Exception as e:
                log.exception("PROMPT function error")
                return "[Error: %s]" % str(e)

        # ── XServiceInfo ──────────────────────────────────────────

        def getImplementationName(self):
            return "org.extension.localwriter.PromptFunction"

        def supportsService(self, name):
            return name in self.getSupportedServiceNames()

        def getSupportedServiceNames(self):
            return ("com.sun.star.sheet.AddIn",)

    g_ImplementationHelper = unohelper.ImplementationHelper()
    g_ImplementationHelper.addImplementation(
        PromptFunction,
        "org.extension.localwriter.PromptFunction",
        ("com.sun.star.sheet.AddIn",),
    )

except ImportError:
    # Not running inside LibreOffice
    pass
