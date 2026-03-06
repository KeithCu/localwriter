import time
import unittest
from unittest.mock import MagicMock
from plugin.modules.calc.manipulator import CellManipulator

class MockBridge:
    def __init__(self):
        self.doc = MagicMock()
        self.sheet = MagicMock()
        self.cell_range = MagicMock()

        # Mock formats
        self.formats = MagicMock()
        self.formats.queryKey.return_value = -1
        self.formats.addNew.return_value = 42
        self.doc.getNumberFormats.return_value = self.formats
        self.doc.getPropertyValue.return_value = "en_US"

        # Track cells to simulate overhead
        self.cells = {}

    def get_active_sheet(self):
        return self.sheet

    def get_active_document(self):
        return self.doc

    def parse_range_string(self, range_str):
        # Assume A1:CV100 -> cols 0 to 99, rows 0 to 99
        return (0, 0), (99, 99)

    def get_cell_range(self, sheet, range_str):
        return self.cell_range

# Create mock bridge and inject
bridge = MockBridge()

def mock_get_cell(col, row):
    # Simulate a small delay for API call
    # time.sleep(0.00001)
    if (col, row) not in bridge.cells:
        cell = MagicMock()
        bridge.cells[(col, row)] = cell
    return bridge.cells[(col, row)]

bridge.sheet.getCellByPosition.side_effect = mock_get_cell

manipulator = CellManipulator(bridge)

print("Starting benchmark...")
start_time = time.time()
manipulator._set_range_number_format("A1:CV100", "#,##0.00")
end_time = time.time()

print(f"Time taken: {end_time - start_time:.4f} seconds")
print(f"getCellByPosition called {bridge.sheet.getCellByPosition.call_count} times")
print(f"setPropertyValue called on cells: {sum(c.setPropertyValue.call_count for c in bridge.cells.values())} times")
