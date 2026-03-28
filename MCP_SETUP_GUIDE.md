# WriterAgent MCP Server Setup Guide

## ✅ Status: MCP Server is Running!

The WriterAgent MCP server is **already enabled and running** on:
- **URL**: `http://localhost:8765/mcp`
- **Status**: Healthy ✅
- **Available tools**: 17 Writer tools, plus Calc and Draw tools

## Quick Verification

```bash
# Check server health
curl -s http://localhost:8765/health | python3 -m json.tool

# List available tools
curl -s http://localhost:8765/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | python3 -m json.tool
```

## Available Tools

### Writer Tools (17)
keep - `apply_document_content` - Insert/replace content with HTML
- `clone_heading_block` - Clone heading + subheadings
- `delete_paragraph` - Delete paragraphs
- `duplicate_paragraph` - Duplicate paragraphs
keep - `get_document_content` - Get document/selection content
keep - `get_document_stats` - Document statistics
- `insert_at_paragraph` - Insert text at specific location
- `insert_paragraphs_batch` - Batch insert multiple paragraphs
- `modify_paragraph` - Modify paragraph text/style
- `read_paragraphs` - Read paragraph ranges
keep- `generate_image` - Generate/edit images
keep- `get_document_tree` - Get heading tree structure
keep- `get_index_stats` - Search index statistics
keep- `search_in_document` - Search text
keep - `get_style_info` - Get style properties
keep - `list_styles` - List available styles
keep - `web_research` - Web search tool

### Calc Tools (18)
Full spreadsheet manipulation including cells, formulas, sheets, charts, and conditional formatting.

### Draw/Impress Tools (12)
Slide management, shape manipulation, and presentation tools.

## MCP Protocol Usage

### JSON-RPC 2.0 Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### Methods

1. **`tools/list`** - List available tools
2. **`tools/call`** - Execute a tool

### Example: Call a Tool

```bash
curl -s http://localhost:8765/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_document_stats",
      "arguments": {}
    }
  }' \
  | python3 -m json.tool
```

### Document Targeting

Use the `X-Document-URL` header to target specific documents:

```bash
curl -s http://localhost:8765/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Document-URL: file:///path/to/document.odt" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Python Client Example

```python
import requests
import json

def call_mcp(method, params=None, document_url=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    
    headers = {"Content-Type": "application/json"}
    if document_url:
        headers["X-Document-URL"] = document_url
    
    response = requests.post(
        "http://localhost:8765/mcp",
        json=payload,
        headers=headers
    )
    return response.json()

# List tools
tools = call_mcp("tools/list")

# Call a tool
result = call_mcp("tools/call", {
    "name": "get_document_stats",
    "arguments": {}
})
```

## Integration with AI Clients

### Claude Desktop

Create a proxy script to adapt HTTP to stdio:

```python
#!/usr/bin/env python3
# mcp_proxy.py
import sys, json, requests

for line in sys.stdin:
    req = json.loads(line)
    if req["method"] == "tools/list":
        r = requests.post("http://localhost:8765/mcp", json={
            "jsonrpc": "2.0", "id": req["id"], "method": "tools/list"
        })
        print(json.dumps({"id": req["id"], "result": r.json()["result"]}))
    # ... handle other methods
    sys.stdout.flush()
```

### Cursor

Cursor can connect directly to the HTTP endpoint:
- **MCP Endpoint**: `http://localhost:8765/mcp`
- **Protocol**: JSON-RPC 2.0

### Custom Scripts

Use the Python example above or any HTTP client library.

## Configuration

The MCP server is configured in WriterAgent Settings:
- **Enable MCP Server**: ✅ Enabled
- **MCP Port**: 8765
- **Bind Address**: localhost (secure, no external access)

## Security Notes

- ✅ Localhost-only binding (no external network access)
- ✅ No authentication (local machine access only)
- ✅ Opt-in feature (disabled by default in fresh installations)
- ✅ All operations require LibreOffice to be running

## Troubleshooting

### Server not responding

1. Check if WriterAgent is running: `ps aux | grep libreoffice`
2. Verify MCP is enabled in WriterAgent Settings
3. Check the port: `netstat -tuln | grep 8765`
4. View logs: `~/writeragent_debug.log`

### Tools not working

1. Ensure a document is open in LibreOffice
2. Use `X-Document-URL` header for specific documents
3. Check tool parameters match the schema

## Files Created

- `test_mcp_connection.py` - Basic connection test
- `example_mcp_usage.py` - Comprehensive usage examples
- `MCP_SETUP_GUIDE.md` - This guide

## Next Steps

1. ✅ Verify MCP server is running (DONE)
2. ✅ Test tool listing (DONE)
3. ✅ Test tool execution (DONE)
4. ✅ Create example scripts (DONE)
5. ✅ Document the setup (DONE)

The MCP server is fully operational and ready for integration with external AI clients!
