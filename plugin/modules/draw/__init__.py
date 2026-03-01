"""Draw module — tools for Draw/Impress document manipulation."""

from plugin.framework.module_base import ModuleBase


class DrawModule(ModuleBase):
    """Registers Draw/Impress tools for shapes, pages/slides."""

    def initialize(self, services):
        self.services = services
