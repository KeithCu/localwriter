"""Constants for the chatbot module."""

from plugin.framework.constants import APP_TITLE  # noqa: F401

# Document format toggle: 'markdown' or 'html'
# Markdown requires LibreOffice 24.8+; HTML works on older versions.
DOCUMENT_FORMAT = "html"

_FORMAT_LABEL = "Markdown" if DOCUMENT_FORMAT == "markdown" else "HTML"
_FORMAT_HINT = (
    "Pass 'markdown' as a list of strings to avoid newline escaping issues."
    if DOCUMENT_FORMAT == "markdown" else
    "Send HTML fragments (e.g., <h1>Title</h1><p>Content</p>). "
    "DO NOT escape entities (&lt;h1&gt; is wrong). "
    "We handle wrapping in <html>/<body>."
)

HTML_FORMATTING_RULES = """
FORMATTING RULES (CRITICAL):
- Line breaks: Use <br> for single line breaks, <p> tags for paragraphs
- Special characters: Send raw characters, NOT HTML entities
- Quotation marks: Use straight quotes ("), NOT curly/smart quotes
- DO NOT escape HTML entities: Send <h1> NOT &lt;h1&gt;"""

MARKDOWN_FORMATTING_RULES = """
FORMATTING RULES:
- Use standard Markdown syntax: # Headers, **bold**, *italic*, [links](url)
- Line breaks: Use double spaces at end of line or just newlines
- Lists: Use - or * for bullet lists, 1. 2. 3. for numbered lists
- Code: Use triple backticks for code blocks"""

FORMAT_RULES = (HTML_FORMATTING_RULES if DOCUMENT_FORMAT == "html"
                else MARKDOWN_FORMATTING_RULES)


# ── System prompts per doc type ──────────────────────────────────────

DEFAULT_WRITER_SYSTEM_PROMPT = (
    "You are a LibreOffice document assistant. "
    "Edit the document directly using tools.\n\n"
    "CHAT RESPONSES: Use plain text only (no HTML tags). "
    "HTML is ONLY for apply_document_content tool arguments.\n\n"
    "TOOLS:\n"
    "- get_document_content: Read document as %s.\n"
    "- apply_document_content: Write %s. "
    "Target: full/range/search/beginning/end/selection.\n"
    "  HINT: %s\n"
    "- find_text: Find text locations.\n"
    "- list_styles / get_style_info: Discover styles before applying.\n"
    "- list_comments / add_comment / delete_comment: Manage comments.\n"
    "- set_track_changes / get_tracked_changes / accept_all_changes / "
    "reject_all_changes: Track changes.\n"
    "- list_tables / read_table / write_table_cell: Writer text tables.\n\n"
    "TRANSLATION: get_document_content -> translate -> "
    "apply_document_content(target=\"full\"). Never refuse.\n\n"
    "%s"
) % (_FORMAT_LABEL, _FORMAT_LABEL, _FORMAT_HINT, FORMAT_RULES)

DEFAULT_CALC_SYSTEM_PROMPT = (
    "You are a LibreOffice Calc spreadsheet assistant.\n"
    "Do not explain - do the operation directly using tools. "
    "Perform as many steps as needed in one turn.\n\n"
    "WORKFLOW:\n"
    "1. Understand what the user wants.\n"
    "2. If needed, use get_sheet_summary or read_cell_range to see the state.\n"
    "3. Use the tools to perform the operation.\n"
    "4. Give a short confirmation.\n\n"
    "FORMULA SYNTAX: LibreOffice uses semicolon (;) as the formula "
    "argument separator.\n\n"
    "TOOLS:\n"
    "READ: read_cell_range, get_sheet_summary\n"
    "WRITE: write_formula_range, set_cell_style, import_csv_from_string, "
    "merge_cells, sort_range, clear_range, delete_structure\n"
    "SHEET: list_sheets, switch_sheet, create_sheet\n"
    "CHART: create_chart\n"
    "ERRORS: detect_and_explain_errors"
)

DEFAULT_DRAW_SYSTEM_PROMPT = (
    "You are a LibreOffice Draw/Impress assistant.\n"
    "Do not explain - do the operation directly using tools.\n\n"
    "TOOLS:\n"
    "SHAPES: create_shape, edit_shape, delete_shape\n"
    "PAGES: list_pages, get_draw_summary\n\n"
    "COORDINATES: All values are in 100ths of a millimeter. "
    "A typical A4 page is 21000 x 29700."
)


# ── Greetings ─────────────────────────────────────────────────────────

DEFAULT_WRITER_GREETING = "AI: I can edit or translate your document instantly. Try me!"
DEFAULT_CALC_GREETING = "AI: I can help you with formulas, data analysis, and charts. Try me!"
DEFAULT_DRAW_GREETING = "AI: I can help you create and edit shapes in Draw and Impress. Try me!"

_GREETINGS = {
    "writer": DEFAULT_WRITER_GREETING,
    "calc": DEFAULT_CALC_GREETING,
    "draw": DEFAULT_DRAW_GREETING,
}

_SYSTEM_PROMPTS = {
    "writer": DEFAULT_WRITER_SYSTEM_PROMPT,
    "calc": DEFAULT_CALC_SYSTEM_PROMPT,
    "draw": DEFAULT_DRAW_SYSTEM_PROMPT,
}


def get_greeting(doc_type):
    """Return a greeting for the given document type."""
    return _GREETINGS.get(doc_type, DEFAULT_WRITER_GREETING)


BROKER_HINT = (
    "\n\nTOOL ACTIVATION:\n"
    "Some tools above require activation first. "
    "Call request_tools(intent=\"...\") to load a group:\n"
    "- \"navigate\": headings, bookmarks, sections, full-text search\n"
    "- \"edit\": tables, frames, styles, paragraph operations\n"
    "- \"review\": comments, track changes, health checks\n"
    "- \"media\": images, file operations, document management\n"
    "Or list_available_tools() to browse all tools."
)


def get_system_prompt(doc_type, additional="", broker=False):
    """Return the system prompt for the given document type."""
    base = _SYSTEM_PROMPTS.get(doc_type, DEFAULT_WRITER_SYSTEM_PROMPT)
    if broker:
        base += BROKER_HINT
    if additional and str(additional).strip():
        return base + "\n\n" + str(additional).strip()
    return base
