"""
Fixed examples for DSPy prompt optimization.
Each example has document_content (the in-memory "document") and user_question.
Optional: expected_contains (list of strings that must appear in final doc) for metric.
"""
import sys
from pathlib import Path

# Allow importing from repo root (for constants)
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from core.constants import FORMAT_RULES
except Exception:
    FORMAT_RULES = ""

# ---------------------------------------------------------------------------
# 1. Table from mess (cleanup and make pretty)
# ---------------------------------------------------------------------------
MESSY_TABLE_INPUT = """* Battery|Battle Born BB5024H (24V 50Ah Heated)|$999.00[3]|The heart of the system. 10-year warranty.

Controller|Victron SmartSolar MPPT 100/30|$135.15[2]|Handles the 440W panel easily at 24V.

* USB Charger|Blue Sea Systems 1045 (4.8A)|$43.00|Industrial grade. Accepts 24V input directly.

Tycon TP-DCDC-1224G-4P|$66.00|Critical: Stabilizes 24V battery voltage (which swings 20V-29V) to a clean 24V PoE for the Ubiquiti.

* USB Charger|Blue Sea Systems 1045 (4.8A)|$43.00|Industrial grade. Accepts 24V input directly.

Enclosure|Saginaw SCE-202010ELJ|$215.31|20x20x10 NEMA 4 steel box.
"""

TABLE_FROM_MESS = {
    "document_content": MESSY_TABLE_INPUT,
    "user_question": "Cleanup and make pretty.",
    "task_id": "table_from_mess",
    "expected_contains": ["Battle Born", "Victron", "SmartSolar", "NEMA 4"],
}

# ---------------------------------------------------------------------------
# 2. Reformat resume
# ---------------------------------------------------------------------------
PLAIN_RESUME = """john doe
john@example.com  |  555-1234

WORK HISTORY
* acme corp 2020-2023  developer
  built apis and fixed bugs  led 2 junior devs

* techstart inc  2023-present  senior developer
  microservices  ci/cd  on-call rotation
  no bullets here just run-on

EDUCATION
state university  bs computer science 2016  gpa 3.8

* skills
python  java  sql  docker  kubernetes
"""

REFORMAT_RESUME = {
    "document_content": PLAIN_RESUME,
    "user_question": "Reformat this plain text resume as professional. Use clear section headings and consistent formatting.",
    "task_id": "reformat_resume",
    "expected_contains": ["John", "Work", "Skills", "Education", "Acme", "TechStart"],
}

# ---------------------------------------------------------------------------
# 3. Table Engineering (CSV-like to table)
# ---------------------------------------------------------------------------
CSV_LIKE = """Fruit, Price, Qty
Apple, 1.20, 12
Banana, 0.50, 24
Orange, 0.80
Grape, 2.00, 8
Mango, 1.50, 6,
"""

TABLE_ENGINEERING = {
    "document_content": CSV_LIKE,
    "user_question": "Convert this comma-separated list into a clean table with headers (Item, Price, Quantity). Fix missing or extra commas.",
    "task_id": "table_engineering",
    "expected_contains": ["Item", "Price", "Quantity"],
}

# ---------------------------------------------------------------------------
# 4. Bulk Cleanup
# ---------------------------------------------------------------------------
DOUBLE_SPACE_TEXT = """This  sentence   has    extra   spaces.  So  does  this  one..
Another   paragraph   here  ,  with spaces before commas.  Fix  all  double  spaces  and  ensure  one  space  after  sentences.


Too many line breaks above  .  Normalize to single paragraph breaks.
"""

BULK_CLEANUP = {
    "document_content": DOUBLE_SPACE_TEXT,
    "user_question": "Remove all double spaces, fix punctuation (no space before comma, no double periods), and normalize line breaks to single paragraph breaks.",
    "task_id": "bulk_cleanup",
    "expected_contains": [],
    "reject_contains": ["  ", " .", "..", " ,"],  # no double spaces, space-before-period, double period, space before comma
}

# ---------------------------------------------------------------------------
# 5. Logical Rewriting
# ---------------------------------------------------------------------------
TECH_PARAGRAPH = """The API utilizes a RESTful architecture and supports JSON serialization. We have implemented OAuth2 for authentication and rate limiting to prevent abuse. The SDK is available for Python and JavaScript."""

LOGICAL_REWRITING = {
    "document_content": TECH_PARAGRAPH,
    "user_question": "Rewrite this paragraph to be professional and concise while preserving all technical terms (API, RESTful, JSON, OAuth2, SDK).",
    "task_id": "logical_rewriting",
    "expected_contains": ["API", "RESTful", "JSON", "OAuth2", "SDK"],
}

# ---------------------------------------------------------------------------
# 6. Format Preservation (replace text)
# ---------------------------------------------------------------------------
HEADER_TEXT = "John Doe - Project Lead"

FORMAT_PRESERVATION = {
    "document_content": HEADER_TEXT,
    "user_question": "Replace 'John Doe' with 'Jane Smith' in the header.",
    "task_id": "format_preservation",
    "expected_contains": ["Jane Smith"],
    "reject_contains": ["John Doe"],
}

# ---------------------------------------------------------------------------
# 7. Style Application (heading)
# ---------------------------------------------------------------------------
INTRO_TEXT = "Introduction\n\nThis document describes the system."

STYLE_APPLICATION = {
    "document_content": INTRO_TEXT,
    "user_question": "Make 'Introduction' a Heading 1.",
    "task_id": "style_application",
    "expected_contains": ["Introduction"],
}

# ---------------------------------------------------------------------------
# 8. Bullet consistency
# ---------------------------------------------------------------------------
BULLET_LIST = """- First item
- Second item
- Third item
"""

BULLET_CONSISTENCY = {
    "document_content": BULLET_LIST,
    "user_question": "Ensure all bullet points in this list end with a period.",
    "task_id": "bullet_consistency",
    "expected_contains": ["First item.", "Second item.", "Third item."],
}

# ---------------------------------------------------------------------------
# All examples (for train/val split)
# ---------------------------------------------------------------------------
ALL_EXAMPLES = [
    TABLE_FROM_MESS,
    REFORMAT_RESUME,
    TABLE_ENGINEERING,
    BULK_CLEANUP,
    LOGICAL_REWRITING,
    FORMAT_PRESERVATION,
    STYLE_APPLICATION,
    BULLET_CONSISTENCY,
]


def to_dspy_examples(examples=None, with_inputs=True):
    """Convert dict examples to dspy.Example objects. Requires dspy."""
    import dspy
    if examples is None:
        examples = ALL_EXAMPLES
    out = []
    for ex in examples:
        e = dspy.Example(
            document_content=ex["document_content"],
            user_question=ex["user_question"],
            task_id=ex.get("task_id", ""),
            expected_contains=ex.get("expected_contains", []),
            reject_contains=ex.get("reject_contains", []),
        ).with_inputs("document_content", "user_question") if with_inputs else dspy.Example(**ex)
        out.append(e)
    return out


def get_trainset_valset(split=0.8, seed=42):
    """Split ALL_EXAMPLES into train and val. Returns (trainset, valset) as list of dicts."""
    import random
    rng = random.Random(seed)
    indices = list(range(len(ALL_EXAMPLES)))
    rng.shuffle(indices)
    n = int(len(ALL_EXAMPLES) * split)
    train_idx = set(indices[:n])
    trainset = [ALL_EXAMPLES[i] for i in range(len(ALL_EXAMPLES)) if i in train_idx]
    valset = [ALL_EXAMPLES[i] for i in range(len(ALL_EXAMPLES)) if i not in train_idx]
    return trainset, valset
