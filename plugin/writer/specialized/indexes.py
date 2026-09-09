# WriterAgent - AI Writing Assistant for LibreOffice
# Copyright (c) 2024 John Balis
# Copyright (c) 2026 KeithCu (modifications and relicensing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Writer document indexes (TOC, bibliography) — specialized indexes domain.

Bibliography v1 is an indexes overload, not ``domain=bibliography``. Cites are
``com.sun.star.text.textfield.Bibliography`` (a TextField), not index marks.
The reference table is ``indexes_create(kind="bibliography")``. After cite
changes, ``indexes_update_all`` refreshes that table.
"""

from typing import Any

from ..specialized_base import ToolWriterIndexBase
from ..target_resolver import resolve_target_cursor

# Creation service → indexes_create kind. Prefer XDocumentIndex.getServiceName()
# when listing: bibliography tables implement SwXDocumentIndex (same as
# alphabetical), so getImplementationName() alone remaps them wrongly.
_INDEX_SERVICE_TO_KIND = {
    "com.sun.star.text.ContentIndex": "toc",
    "com.sun.star.text.DocumentIndex": "alphabetical",
    "com.sun.star.text.UserIndex": "user",
    "com.sun.star.text.IllustrationsIndex": "illustration",
    "com.sun.star.text.TableIndex": "table",
    "com.sun.star.text.ObjectIndex": "object",
    "com.sun.star.text.Bibliography": "bibliography",
}

# Fallback only. SwXDocumentIndex is shared by alphabetical *and* bibliography.
_INDEX_IMPL_TO_KIND = {
    "SwXContentIndex": "toc",
    "SwXDocumentIndex": "alphabetical",
    "SwXUserIndex": "user",
}

# Live LO (sw/source/core/fields/authfld.cxx aFieldNames). PropertyValue.Name is
# the pretty string, not IDENTIFIER. Type is BibiliographicType (IDL typo
# BIBILIOGRAPHIC_TYPE — one L missing, "Bibi…" not "Biblio…").
_BIB_FIELD_NAMES = (
    "Identifier",
    "BibiliographicType",
    "Address",
    "Annote",
    "Author",
    "Booktitle",
    "Chapter",
    "Edition",
    "Editor",
    "Howpublished",
    "Institution",
    "Journal",
    "Month",
    "Note",
    "Number",
    "Organizations",
    "Pages",
    "Publisher",
    "School",
    "Series",
    "Title",
    "Report_Type",
    "Volume",
    "Year",
    "URL",
    "Custom1",
    "Custom2",
    "Custom3",
    "Custom4",
    "Custom5",
    "ISBN",
    "LocalURL",
    "TargetType",
    "TargetURL",
)

_BIB_FIELD_NAME_SET = frozenset(_BIB_FIELD_NAMES)

# Convenience / IDL / English aliases → live Fields names. Unused kinds ignore
# these kwargs; v2 keys (zotero_key, citekey, locator, csl_style) stay unmapped.
_BIB_FIELD_ALIASES = {
    "identifier": "Identifier",
    "author": "Author",
    "title": "Title",
    "year": "Year",
    "pages": "Pages",
    "isbn": "ISBN",
    "url": "URL",
    "booktitle": "Booktitle",
    "publisher": "Publisher",
    "bibiliographictype": "BibiliographicType",
    "bibliographictype": "BibiliographicType",
    "bibliographic_type": "BibiliographicType",
    "bibiliographic_type": "BibiliographicType",
    "bibilographic_type": "BibiliographicType",
}

# BibliographyDataType constants (book=1 matches Insert → Bibliographic Entry).
_BIB_TYPE_NAMES = {
    "article": 0,
    "book": 1,
    "booklet": 2,
    "conference": 3,
    "inbook": 4,
    "incollection": 5,
    "inproceedings": 6,
    "journal": 7,
    "manual": 8,
    "mastersthesis": 9,
    "misc": 10,
    "phdthesis": 11,
    "proceedings": 12,
    "techreport": 13,
    "unpublished": 14,
    "email": 15,
    "www": 16,
}

_BIB_CITE_SERVICE = "com.sun.star.text.textfield.Bibliography"
_BIB_CITE_SERVICE_ALT = "com.sun.star.text.TextField.Bibliography"
_IGNORED_CITE_KWARGS = frozenset({"zotero_key", "citekey", "locator", "csl_style"})


def canonicalize_bibliography_field_name(name: str) -> str | None:
    """Map a model/IDL alias to the live Fields PropertyValue.Name, or None."""
    raw = (name or "").strip()
    if not raw:
        return None
    if raw in _BIB_FIELD_NAME_SET:
        return raw
    folded = raw.replace("-", "_")
    alias = _BIB_FIELD_ALIASES.get(folded.lower())
    if alias:
        return alias
    # IDENTIFIER → Identifier, BIBILIOGRAPHIC_TYPE → BibiliographicType
    if "_" in folded:
        parts = [p for p in folded.split("_") if p]
        pretty = "".join(p[:1].upper() + p[1:].lower() for p in parts)
        if pretty == "BibilographicType":
            pretty = "BibiliographicType"
        if pretty in _BIB_FIELD_NAME_SET:
            return pretty
    titled = raw[:1].upper() + raw[1:] if raw else raw
    if titled in _BIB_FIELD_NAME_SET:
        return titled
    return None


def resolve_bibliographic_type(value: Any) -> int | None:
    """Coerce a type hint to BibliographyDataType (int). None if unused/invalid."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return _BIB_TYPE_NAMES.get(text.lower().replace(" ", "").replace("-", ""))


def collect_bibliography_field_pairs(kwargs: dict[str, Any]) -> list[tuple[str, Any]]:
    """Build (Name, Value) pairs for Fields. Later keys override earlier ones."""
    pairs: dict[str, Any] = {}
    extra = kwargs.get("fields")
    if isinstance(extra, dict):
        for key, value in extra.items():
            canon = canonicalize_bibliography_field_name(str(key))
            if canon is None or value is None:
                continue
            pairs[canon] = value

    convenience = (
        ("identifier", kwargs.get("identifier")),
        ("author", kwargs.get("author")),
        ("title", kwargs.get("title")),
        ("year", kwargs.get("year")),
        ("pages", kwargs.get("pages")),
    )
    for alias, value in convenience:
        if value is None or value == "":
            continue
        pairs[_BIB_FIELD_ALIASES[alias]] = value

    type_val = resolve_bibliographic_type(
        kwargs.get("bibliographic_type", kwargs.get("bibiliographic_type"))
    )
    if type_val is not None:
        pairs["BibiliographicType"] = type_val

    if "Identifier" not in pairs or pairs["Identifier"] in (None, ""):
        text = kwargs.get("text")
        if text not in (None, ""):
            pairs["Identifier"] = text

    out: list[tuple[str, Any]] = []
    for name, value in pairs.items():
        if value is None:
            continue
        if name == "BibiliographicType":
            resolved = resolve_bibliographic_type(value)
            if resolved is None:
                continue
            out.append((name, resolved))
            continue
        # Year and the rest of the bag are strings in SwAuthorityField::QueryValue.
        out.append((name, str(value)))
    return out


def fields_sequence_to_dict(raw: Any) -> dict[str, Any]:
    """Map a Fields PropertyValue sequence to {Name: Value} (non-empty only)."""
    result: dict[str, Any] = {}
    if not raw:
        return result
    try:
        items = list(raw)
    except TypeError:
        return result
    for item in items:
        name = getattr(item, "Name", None)
        if not name:
            continue
        value = getattr(item, "Value", None)
        if value in (None, ""):
            continue
        result[str(name)] = value
    return result


def index_kind_from_uno(idx: Any) -> str:
    """Prefer getServiceName(); fall back to the old SwX* remaps."""
    service = None
    if hasattr(idx, "getServiceName"):
        try:
            service = idx.getServiceName()
        except Exception:
            service = None
    if isinstance(service, str) and service in _INDEX_SERVICE_TO_KIND:
        return _INDEX_SERVICE_TO_KIND[service]

    impl = None
    if hasattr(idx, "getImplementationName"):
        try:
            impl = idx.getImplementationName()
        except Exception:
            impl = None
    if isinstance(impl, str) and impl in _INDEX_IMPL_TO_KIND:
        return _INDEX_IMPL_TO_KIND[impl]
    if isinstance(impl, str) and impl:
        return impl
    if isinstance(service, str) and service:
        return service
    return "unknown"


def is_bibliography_text_field(field: Any) -> bool:
    """True for native Writer bibliography cite fields (not the index table)."""
    if field is None:
        return False
    if hasattr(field, "supportsService"):
        for service in (_BIB_CITE_SERVICE, _BIB_CITE_SERVICE_ALT):
            try:
                if field.supportsService(service):
                    return True
            except Exception:
                continue
    return False


def _create_property_value(name: str, value: Any) -> Any:
    import uno

    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


def set_bibliography_field_values(field: Any, pairs: list[tuple[str, Any]]) -> None:
    """Write Fields as a typed UNO sequence.

    A Python tuple passed to ``setPropertyValue("Fields", …)`` is accepted and
    silently dropped. ``uno.Any("[]com.sun.star.beans.PropertyValue", seq)``
    must go through ``uno.invoke`` (same pattern as CustomShapeGeometry).
    Set this on the descriptor *before* insert so attach() applies aPropSeq.
    """
    import uno
    from typing import cast

    uno_any = getattr(uno, "Any")
    seq = tuple(_create_property_value(name, value) for name, value in pairs)
    typed = uno_any("[]com.sun.star.beans.PropertyValue", cast("object", seq))
    uno.invoke(field, "setPropertyValue", cast("object", ("Fields", typed)))


class IndexesUpdateAll(ToolWriterIndexBase):
    name = "indexes_update_all"
    intent = "navigate"
    description = (
        "Refresh all document indexes (TOC, alphabetical, bibliography table). "
        "Call after inserting or editing bibliography cites so the reference list updates."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_mutation = True

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getDocumentIndexes"):
            return self._tool_error("Document does not support indexes")
        indexes = doc.getDocumentIndexes()
        count = indexes.getCount()
        refreshed = []
        for i in range(count):
            idx = indexes.getByIndex(i)
            idx.update()
            name = idx.getName() if hasattr(idx, "getName") else "index_%d" % i
            refreshed.append(name)
        return {"status": "ok", "refreshed": refreshed, "count": count}


class IndexesList(ToolWriterIndexBase):
    name = "indexes_list"
    intent = "navigate"
    description = (
        "List document indexes (TOC, alphabetical, user, bibliography tables). "
        "type matches indexes_create kind (bibliography via getServiceName). "
        "For in-flow cites use indexes_list_cites, not this tool."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_mutation = False

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getDocumentIndexes"):
            return self._tool_error("Document does not support indexes")
        indexes = doc.getDocumentIndexes()
        count = indexes.getCount()
        result = []
        for i in range(count):
            idx = indexes.getByIndex(i)
            name = idx.getName() if hasattr(idx, "getName") else f"index_{i}"
            title = idx.Title if hasattr(idx, "Title") else ""
            result.append({
                "index": i,
                "name": name,
                "title": title,
                "type": index_kind_from_uno(idx),
            })
        return {"status": "ok", "indexes": result, "count": count}


class IndexesListCites(ToolWriterIndexBase):
    name = "indexes_list_cites"
    intent = "examine"
    description = (
        "List native bibliography cite fields (TextField.Bibliography). "
        "Returns identifier, key Fields (Author, Title, Year, Pages, type), and location. "
        "Does not list the bibliography table — use indexes_list for that."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_mutation = False

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getTextFields"):
            return self._tool_error("Document does not support text fields")

        from ..search import describe_match_location

        fields = doc.getTextFields()
        enum = fields.createEnumeration()
        cites = []
        hf_labels = {}
        scanned = 0
        while enum.hasMoreElements():
            field = enum.nextElement()
            scanned += 1
            if not is_bibliography_text_field(field):
                continue
            mapped = {}
            try:
                mapped = fields_sequence_to_dict(field.getPropertyValue("Fields"))
            except Exception:
                mapped = {}
            try:
                location = describe_match_location(field.getAnchor(), doc, hf_labels)
            except Exception:
                location = "unknown"
            try:
                presentation = field.getPresentation(False)
            except Exception:
                presentation = ""
            cites.append({
                "id": len(cites) + 1,
                "identifier": str(mapped.get("Identifier") or ""),
                "author": mapped.get("Author", ""),
                "title": mapped.get("Title", ""),
                "year": mapped.get("Year", ""),
                "pages": mapped.get("Pages", ""),
                "bibliographic_type": mapped.get("BibiliographicType"),
                "fields": mapped,
                "location": location,
                "presentation": presentation,
            })
        return {"status": "ok", "cites": cites, "count": len(cites), "fields_scanned": scanned}


class IndexesCreate(ToolWriterIndexBase):
    name = "indexes_create"
    intent = "edit"
    description = (
        "Create a document index (toc, alphabetical, user, illustration, table, object, bibliography). "
        "kind=bibliography inserts the reference table (com.sun.star.text.Bibliography); "
        "cites must already exist or be added with indexes_add_mark kind=bibliography, then indexes_update_all. "
        "Use target='beginning', 'end', or 'selection'. "
        "Use target='search' with old_content to find and replace text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["toc", "alphabetical", "user", "illustration", "table", "object", "bibliography"], "description": "The type of index to create."},
            "title": {"type": "string", "description": "The title for the index (e.g., 'Table of Contents')."},
            "create_from_outline": {"type": "boolean", "description": "Whether to create the index from the document outline (mainly for toc). Default true."},
            "target": {"type": "string", "enum": ["beginning", "end", "selection", "full_document", "search"], "description": "Where to insert the index."},
            "old_content": {"type": "string", "description": "Text to find and replace if target = 'search'."},
        },
        "required": ["kind"],
    }
    is_mutation = True

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        index_kind = kwargs.get("kind", "toc")
        title = kwargs.get("title")
        create_from_outline = kwargs.get("create_from_outline", True)
        target = kwargs.get("target", "selection")
        old_content = kwargs.get("old_content")

        try:
            service_map = {
                "toc": "com.sun.star.text.ContentIndex",
                "alphabetical": "com.sun.star.text.DocumentIndex",
                "user": "com.sun.star.text.UserIndex",
                "illustration": "com.sun.star.text.IllustrationsIndex",
                "table": "com.sun.star.text.TableIndex",
                "object": "com.sun.star.text.ObjectIndex",
                "bibliography": "com.sun.star.text.Bibliography",
            }
            service_name = service_map.get(index_kind, "com.sun.star.text.ContentIndex")

            index = doc.createInstance(service_name)
            if title is not None and hasattr(index, "Title"):
                index.Title = title

            if index_kind == "toc" and hasattr(index, "CreateFromOutline"):
                index.CreateFromOutline = create_from_outline

            try:
                cursor = resolve_target_cursor(ctx, target, old_content)
            except ValueError as ve:
                return self._tool_error(str(ve))

            if not cursor:
                return self._tool_error("Failed to resolve target location.")

            if target == "search" and old_content:
                cursor.setString("")

            text = cursor.getText()
            text.insertTextContent(cursor, index, False)
            index.update()

            return {"status": "ok", "message": f"Created '{index_kind}' index successfully", "title": title}
        except Exception as e:
            return self._tool_error(f"Failed to create index: {str(e)}")


class IndexesAddMark(ToolWriterIndexBase):
    name = "indexes_add_mark"
    intent = "edit"
    description = (
        "Insert an index mark or a bibliography cite at target. "
        "kind=alphabetical|user creates DocumentIndexMark / UserIndexMark (primary_key/secondary_key). "
        "kind=bibliography creates TextField.Bibliography — not an index mark; "
        "set Identifier/Author/Title/Year/Pages (text defaults to Identifier). "
        "primary_key is ignored for cites. After cite changes call indexes_update_all "
        "so the bibliography table refreshes. Do not use fields_insert for product cites."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Index mark entry, or Identifier fallback for kind=bibliography."},
            "kind": {
                "type": "string",
                "enum": ["alphabetical", "user", "bibliography"],
                "description": "alphabetical/user = index mark; bibliography = TextField.Bibliography cite.",
            },
            "primary_key": {"type": "string", "description": "Alphabetical index primary key. Ignored for bibliography."},
            "secondary_key": {"type": "string", "description": "Alphabetical index secondary key. Ignored for bibliography."},
            "identifier": {"type": "string", "description": "Cite key (Fields.Identifier). Defaults from text when omitted."},
            "author": {"type": "string", "description": "Cite author. Ignored unless kind=bibliography."},
            "title": {"type": "string", "description": "Cite title. Ignored unless kind=bibliography."},
            "year": {"description": "Cite year (string or integer). Ignored unless kind=bibliography."},
            "pages": {"type": "string", "description": "Cite pages / locator. Ignored unless kind=bibliography."},
            "bibliographic_type": {
                "description": "BibliographyDataType name or int (book, article, …). Ignored unless kind=bibliography.",
            },
            "fields": {
                "type": "object",
                "description": "Extra/override Fields names (Identifier, Author, ISBN, …). Ignored unless kind=bibliography.",
            },
            "target": {"type": "string", "enum": ["beginning", "end", "selection", "full_document", "search"], "description": "Where to insert the mark or cite."},
            "old_content": {"type": "string", "description": "Text to find and replace if target = 'search'."},
        },
        "required": ["text"],
    }
    is_mutation = True

    def execute(self, ctx, **kwargs):
        unused_reserved = [key for key in _IGNORED_CITE_KWARGS if kwargs.get(key) not in (None, "")]
        doc = ctx.doc
        mark_text = kwargs.get("text")
        index_kind = kwargs.get("kind", "alphabetical")
        primary_key = kwargs.get("primary_key")
        secondary_key = kwargs.get("secondary_key")
        target = kwargs.get("target", "selection")
        old_content = kwargs.get("old_content")

        try:
            cursor = resolve_target_cursor(ctx, target, old_content)
        except ValueError as ve:
            return self._tool_error(str(ve))

        if not cursor:
            return self._tool_error("Failed to resolve target location.")

        try:
            if index_kind == "bibliography":
                return self._insert_bibliography_cite(
                    doc, cursor, kwargs, unused_reserved
                )

            service_name = "com.sun.star.text.DocumentIndexMark"
            if index_kind == "user":
                service_name = "com.sun.star.text.UserIndexMark"

            mark = doc.createInstance(service_name)

            if hasattr(mark, "MarkEntry"):
                mark.MarkEntry = mark_text
            elif hasattr(mark, "PrimaryKey") and hasattr(mark, "SecondaryKey"):
                pass  # DocumentIndexMark handles these via properties

            if index_kind == "alphabetical":
                if hasattr(mark, "PrimaryKey") and primary_key is not None:
                    mark.PrimaryKey = primary_key
                if hasattr(mark, "SecondaryKey") and secondary_key is not None:
                    mark.SecondaryKey = secondary_key
                try:
                    mark.setPropertyValue("PrimaryKey", primary_key or "")
                    mark.setPropertyValue("SecondaryKey", secondary_key or "")
                except Exception:
                    pass

            text = cursor.getText()
            text.insertTextContent(cursor, mark, False)

            return {"status": "ok", "message": f"Added '{index_kind}' index mark for '{mark_text}'"}
        except Exception as e:
            return self._tool_error(f"Failed to add index mark: {str(e)}")

    def _insert_bibliography_cite(self, doc, cursor, kwargs, unused_reserved):
        pairs = collect_bibliography_field_pairs(kwargs)
        identifier = ""
        for name, value in pairs:
            if name == "Identifier":
                identifier = str(value)
                break
        if not identifier:
            return self._tool_error(
                "Bibliography cite needs identifier or text (used as Identifier)."
            )

        field = doc.createInstance(_BIB_CITE_SERVICE)
        if not field:
            return self._tool_error("Failed to create textfield.Bibliography")
        # Fields must be set on the descriptor before insert. A plain tuple is
        # dropped; set_bibliography_field_values uses a typed Any via uno.invoke.
        set_bibliography_field_values(field, pairs)
        text = cursor.getText()
        text.insertTextContent(cursor, field, False)
        payload = {
            "status": "ok",
            "message": "Added bibliography cite '%s'" % identifier,
            "kind": "bibliography",
            "identifier": identifier,
            "fields": {name: value for name, value in pairs},
        }
        if unused_reserved:
            payload["ignored"] = unused_reserved
        return payload
