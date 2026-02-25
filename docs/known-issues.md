# Known Issues

## Range coordinate mismatch (Writer)

**Status**: Open — affects `get_document_content(scope="range")` and `apply_document_content(target="range")`.

Character offsets from `find_text` (cursor-based) don't match offsets used by range export (paragraph-enumeration with summed lengths). The same numeric range is interpreted in two different coordinate systems, producing corrupted output (e.g. "## ary..." instead of "## Summary...").

**Recommended fix**: Use cursor-based paragraph offsets — for each enumerated paragraph, measure start/end with `gotoRange(para.getStart(), True)` + `len(cursor.getString())`. This aligns range export with `find_text` coordinates.

**Workaround**: Avoid `scope="range"` for section replacement. Use `target="search"` with full section text instead.

See `legacy_docs/architecture/section-replace-options.md` for detailed analysis of all options.

## AI Horde improvements

Open items for the ai_horde image module:

- **Progress feedback**: Generation can take minutes but sidebar only shows "Running...". The `AiHordeClient` receives progress events — thread them to the UI status bar.
- **Smart image dimensions**: `edit_image` hardcodes replacement to 512x512. Should read the original image dimensions and pass them to the generation request.
- **Translation visibility**: Prompt translation acts silently; show "Translating prompt..." status before generation starts.
