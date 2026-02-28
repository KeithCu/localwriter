"""Calc module — tools for Calc spreadsheet manipulation."""

from plugin.framework.module_base import ModuleBase


class CalcModule(ModuleBase):
    """Registers Calc tools for cells, sheets, formulas, charts."""

    def initialize(self, services):
        self.services = services
