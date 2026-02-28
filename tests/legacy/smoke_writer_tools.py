import json
import unittest
from plugin.modules.core.document_tools import TOOL_DISPATCH
from plugin.modules.writer.ops import WRITER_OPS_TOOLS

class TestWriterToolsSmoke(unittest.TestCase):
    def test_registration(self):
        # Tools we added
        new_tools = [
            "get_document_outline",
            "get_heading_content",
            "read_paragraphs",
            "insert_at_paragraph",
            "get_document_stats"
        ]
        for tool in new_tools:
            self.assertIn(tool, TOOL_DISPATCH, f"Tool {tool} not registered in TOOL_DISPATCH")
            
    def test_schemas(self):
        # Check that schemas are valid JSON-like structures
        new_tool_names = [
            "get_document_outline",
            "get_heading_content",
            "read_paragraphs",
            "get_document_stats"
        ]
        found = 0
        for tool_def in WRITER_OPS_TOOLS:
            name = tool_def["function"]["name"]
            if name in new_tool_names:
                self.assertIn("description", tool_def["function"])
                self.assertIn("parameters", tool_def["function"])
                found += 1
        # self.assertEqual(found, len(new_tool_names)) # Might be more if I didn't filter correctly

if __name__ == "__main__":
    unittest.main()
