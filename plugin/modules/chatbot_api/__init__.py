"""Chatbot REST/SSE API module.

Registers HTTP routes for external clients to interact with the chatbot.
Endpoints:
  POST /api/chat       — send message, stream SSE response
  GET  /api/chat       — get chat history
  DELETE /api/chat     — reset session
  GET  /api/providers  — list available AI providers
"""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.chatbot_api")


class ChatbotApiModule(ModuleBase):
    """Registers chatbot API routes on the HTTP server."""

    def initialize(self, services):
        self._services = services
        self._routes_registered = False

        cfg = services.config.proxy_for(self.name)
        if cfg.get("enabled"):
            self._register_routes(services)

        services.events.subscribe(
            "config:changed", self._on_config_changed)

    def _on_config_changed(self, **kwargs):
        key = kwargs.get("key", "")
        if key != "chatbot_api.enabled":
            return
        enabled = kwargs.get("value")
        if enabled and not self._routes_registered:
            self._register_routes(self._services)
        elif not enabled and self._routes_registered:
            self._unregister_routes(self._services)

    def _register_routes(self, services):
        routes = services.get("http_routes")
        if not routes:
            log.warning("http_routes service not available")
            return

        from plugin.modules.chatbot_api.handler import ChatApiHandler
        self._handler = ChatApiHandler(services)

        routes.add("POST", "/api/chat",
                    self._handler.handle_chat, raw=True)
        routes.add("GET", "/api/chat",
                    self._handler.handle_history)
        routes.add("DELETE", "/api/chat",
                    self._handler.handle_reset)
        routes.add("GET", "/api/providers",
                    self._handler.handle_providers)

        self._routes_registered = True
        log.info("Chat API routes registered")

    def _unregister_routes(self, services):
        routes = services.get("http_routes")
        if routes:
            for method, path in [
                ("POST", "/api/chat"),
                ("GET", "/api/chat"),
                ("DELETE", "/api/chat"),
                ("GET", "/api/providers"),
            ]:
                try:
                    routes.remove(method, path)
                except Exception:
                    pass
        self._routes_registered = False
        log.info("Chat API routes unregistered")
