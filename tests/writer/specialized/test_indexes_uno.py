"""Native tests for indexes bibliography v1 (cite insert, list, table)."""

from plugin.testing_runner import native_test
from plugin.tests.testing_utils import TestingFactory, with_native_doc
from plugin.writer.specialized.indexes import (
    IndexesAddMark,
    IndexesCreate,
    IndexesList,
    IndexesListCites,
    IndexesUpdateAll,
)


def _tool_ctx(ctx, doc):
    return TestingFactory.create_context(doc=doc, ctx=ctx, env="native", doc_type="writer")


@native_test
@with_native_doc("writer")
def test_indexes_cite_insert_list_and_table(ctx, doc):
    """Insert a cite, list it, place the bibliography table, then update."""
    doc.getText().setString("See the climate review. ")
    tctx = _tool_ctx(ctx, doc)

    inserted = IndexesAddMark().execute(
        tctx,
        text="Smith2024",
        kind="bibliography",
        author="Smith, J.",
        title="Climate Notes",
        year="2024",
        pages="12-15",
        bibliographic_type="book",
        target="end",
    )
    assert inserted.get("status") == "ok", inserted
    assert inserted.get("identifier") == "Smith2024"
    assert inserted["fields"]["BibiliographicType"] == 1

    listed = IndexesListCites().execute(tctx)
    assert listed.get("status") == "ok", listed
    assert listed.get("count") == 1
    cite = listed["cites"][0]
    assert cite["identifier"] == "Smith2024"
    assert cite["author"] == "Smith, J."
    assert cite["title"] == "Climate Notes"
    assert cite["year"] == "2024"
    assert cite["pages"] == "12-15"
    assert cite["bibliographic_type"] == 1
    assert cite["presentation"] == "[Smith2024]"
    assert cite["location"]

    created = IndexesCreate().execute(
        tctx, kind="bibliography", title="References", target="end"
    )
    assert created.get("status") == "ok", created

    indexes = IndexesList().execute(tctx)
    assert indexes.get("status") == "ok", indexes
    kinds = [item["type"] for item in indexes["indexes"]]
    assert "bibliography" in kinds, indexes

    refreshed = IndexesUpdateAll().execute(tctx)
    assert refreshed.get("status") == "ok", refreshed

    body = doc.getText().getString()
    assert "Smith2024" in body
    assert "Climate Notes" in body
    assert "2024" in body


@native_test
@with_native_doc("writer")
def test_indexes_list_bibliography_kind_uses_service_name(ctx, doc):
    """getImplementationName() is SwXDocumentIndex; kind must still be bibliography."""
    tctx = _tool_ctx(ctx, doc)
    IndexesCreate().execute(tctx, kind="bibliography", title="Works Cited", target="end")
    listed = IndexesList().execute(tctx)
    assert listed.get("count") >= 1, listed
    bib = next(item for item in listed["indexes"] if item["type"] == "bibliography")
    assert bib["title"] == "Works Cited"
