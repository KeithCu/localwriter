"""Dependency injection container for services."""


class ServiceRegistry:
    """Registry that holds all services and provides attribute access.

    Usage::

        services = ServiceRegistry()
        services.register(my_document_service)
        services.register(my_config_service)

        # Access by name:
        services.document.build_heading_tree(doc)
        services.config.get("mcp.port")

        # Or explicit:
        services.get("document")
    """

    def __init__(self):
        self._services = {}

    def register(self, service):
        """Register a ServiceBase instance by its ``name`` attribute."""
        if service.name is None:
            raise ValueError(f"Service {type(service).__name__} has no name")
        if service.name in self._services:
            raise ValueError(f"Service already registered: {service.name}")
        self._services[service.name] = service

    def register_instance(self, name, instance):
        """Register an arbitrary object as a named service."""
        if name in self._services:
            raise ValueError(f"Service already registered: {name}")
        self._services[name] = instance

    def get(self, name):
        """Get a service by name, or None if not registered."""
        return self._services.get(name)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        svc = self._services.get(name)
        if svc is not None:
            return svc
        raise AttributeError(f"No service registered: {name}")

    def __contains__(self, name):
        return name in self._services

    def initialize_all(self, ctx):
        """Call ``initialize(ctx)`` on every service that supports it."""
        for svc in self._services.values():
            init = getattr(svc, "initialize", None)
            if callable(init):
                init(ctx)

    def shutdown_all(self):
        """Call ``shutdown()`` on every service that supports it."""
        for svc in self._services.values():
            shutdown = getattr(svc, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    pass

    @property
    def service_names(self):
        return list(self._services.keys())
