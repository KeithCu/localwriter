"""Batch module — execute_batch tool for sequential tool chaining."""

from plugin.framework.module_base import ModuleBase


class BatchModule(ModuleBase):
    """Pure tool module — no services to register."""

    def initialize(self, services):
        pass
