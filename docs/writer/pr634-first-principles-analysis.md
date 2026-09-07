# PR #634 follow-ups — first-principles analysis

**Audience:** Keith / Chief / implementers  
**Inputs:** `/workspace/pr634-followups/initial-plan.md`, merged PR [#634](https://github.com/KeithCu/writeragent/pull/634) on `master`  
**Scope:** Research only — no product PR. Goal: proper fixes that stay **simple, robust, and easy for models**.

> **Later product decision:** `apply_style` now defaults to `clear_direct='style_props'` (house font/size win, bold/italic/colour stay). `none` is an explicit opt-in. The same-style-only special case discussed in §2.7 was **not** implemented. Treat sections below that say “default is `none`” as historical.

Symbols and paths below are current `master` unless noted.

---

## 1. Problem framing

### What #634 solved

Augusto’s PR fixed two real agent failure modes with unusual honesty about LibreOffice:

1. **Style apply that looks like success but changes nothing** — Re-applying a paragraph’s existing `ParaStyleName` does **not** clear direct `Char*` (LO 26.2). House-font updates via `style_update("Standard")` + `apply_style("Standard")` left Times-12 standing. #634 added `clear_direct` (`none` / `style_props` / `all`), capture/restore of portion-level Char*, `preserved_char_overrides` hints, and read-side `data-lo-para` from the FODT sidecar so agents can *see* whole-paragraph overrides.

2. **Silent letterhead destruction** — `page_set_header_footer_text` used `XText.setString`, which flattens logos and fields with no signal in `getString()`. #634 scans for fields/images and **refuses** unless `force=true`, points agents at `apply_document_content(target='search')`, and documents first-page regions (`header_first` / `footer_first`).

Compatibility defaults are conservative (`clear_direct` defaults to `none`; overwrite only with `force`). Prompts/docs were updated. Unit/mocks coverage of control flow is dense.

### What remains hazardous for agents

The remaining hazards are mostly **API shape and honesty**, not missing flags:

| Hazard | Why it bites models |
|--------|---------------------|
| Refuse treats **page-number fields like logos** | Normal footer (`Confidential \| Page N`) always errors; only `force` (destructive) is offered as retry |
| Refuse message steers to **document-wide search** | Firm name / “Confidential” hit the **body** first; field presentation `"1"` replaces destroy the field |
| ~~**Region-off** leftover content not scanned~~ | **Not reproduced (F5):** `HeaderText` is `None` when off and empty after off→on, so no leftover exists to scan |
| Scan **does not walk tables** | Letterhead tables (logo \| address) never show as “held”; `setString` flattens them |
| **XText `==` / `!=` for logo anchors** | False “safe” refuse miss → original silent delete |
| Tool **description** still sells overwrite | Models pick tools from descriptions; refuse is buried in `force` + system prompt |
| First-page **logo** still half-reachable | `header_first` writable as text; `image_insert` only `header`/`footer` |
| Default same-style apply still needs a **second** `style_props` call for house font | Lawyer path remains two-step unless we teach the default path |
| Shared text helper **paragraph vs document** walk | `get_string_without_tracked_deletions` on a paragraph injects `\n` between portions |

Expedient patches (“add another prompt line”, “always force”, “always style_props”) feel wrong long-term because they either destroy content, fight preserve-inline tests, or leave the model with two contradictory tools for one intent.

---

## 1.5 Live-verified findings (Sept 2026, dev-host LO)

Probe file: `tests/writer/test_probe_pr634_uno.py` (throwaway probes; to be folded into proper UNO regressions). Values observed on the current dev LibreOffice — re-verify on the runtime the extension actually ships to, which is often older.

| # | Claim tested | Observed | Consequence |
|---|--------------|----------|-------------|
| F1 | Same-style apply drops direct Para* | `ParaLeftMargin` 1500 → 0 on same `ParaStyleName`; also 0 after `Heading 1` | `clear_direct='none'` overclaims indent preservation on any re-apply (§2.7) |
| F2 | Char* on same-style apply | paragraph-wide `CharWeight`/`CharHeight` reset (150→100, 18→12); portion-level bold preserved (150) | same-style house-font fix must *actively clear* font, not just skip restore (§2.7) |
| F3 | Portions surface paragraph-wide Char* | a portion's `CharWeight` reads 150 for a paragraph-wide set | capture cannot distinguish paragraph-wide vs portion-level overrides (§2.7) |
| F4 | `get_string_without_tracked_deletions` on a paragraph | `'Paragraph \nwith n\normal and bold text\n'` (spurious `\n` between runs) | confirms §2.8 |
| F5 | Region-off `HeaderText` | `None` while `HeaderIsOn=False`; `''` after off→on | §2.3 "leftover content" premise does not reproduce (plain text, this build) |

---

## 2. Per open question

### 2.1 Do not treat page-number fields like logos

**Today (`plugin/writer/page.py`)**

- `_scan_region_content` collects **all** `TextPortionType == "TextField"` portions plus draw-page shapes whose anchor text matches the region.
- `_describe_region_contents(scan)` is non-empty if **either** images **or** fields exist.
- `PageSetHeaderFooterText.execute` refuses whenever `held` is non-empty and `force` is false. The error text lists fields and images together and offers: (a) `apply_document_content(target='search')`, or (b) `force=true` to delete them.

**Failure mode**

Office footers are routinely `text + PageNumber field`. After #634 every wording change requires either destroying page numbers (`force`) or a fragile document-wide search. That inverts the real need: **change words, keep fields**.

**Candidate designs**

| Option | Verdict |
|--------|---------|
| A. Keep refuse-on-any-field; improve prompt | **Reject** — prompt cannot invent a safe write path the API doesn’t offer |
| B. Split refuse: images/tables hard-refuse; fields warn but allow `setString` | **Reject** — `setString` still destroys fields; “warn then destroy” is worse honesty |
| C. Refuse images/tables/frames only; for field-only (or text+field) regions, **do not** offer `force` as the primary retry — point to surgical region edit | **Preferred direction** |
| D. Implement `page_replace_header_footer_text(region, old_content, content)` that edits only Text portions inside that `XText`, leaving field portions | **Best long-term**, still small |

**Recommended approach**

1. **Hard refuse** only when the scan finds **images** (and, once implemented, **tables/frames** — §2.3).  
2. **Fields alone do not refuse `page_set`…** *if and only if* we also stop using naive `setString` for that path — otherwise leaving fields un-refused is a lie. So:
   - Short term (honest interim): refuse fields **without** advertising `force` as the fix; error text = “use region-scoped replace / field tools; `force` deletes page numbers.”  
   - Proper fix (still small): add **`page_replace_header_footer_text`** (or extend set with `mode='replace_text'` + `old_content`) that:
     - Resolves only `_REGION_PROPS[region]`’s `XText`
     - Finds `old_content` inside that text object (not `doc.findFirst`)
     - Replaces **Text** portions only; never `setString` the whole region when fields/images exist
3. Keep `force=true` as explicit wipe for “replace entire letterhead with plain text,” reported via existing `deleted` payload.

**Tests**

- UNO: footer with only PageNumber field + surrounding text → replace “Confidential” → field still present; presentation still a number.  
- UNO: footer with AS_CHARACTER logo → plain set without force → refuse; document unchanged (`HeaderIsOn` / height unchanged).  
- UNO: `force=true` with logo → `deleted.images` non-empty; logo gone.

**Residual risk**

Surgical replace must not treat field **presentation** (`"1"`) as replaceable text. Match against visible non-field strings only (same portion filter as the scan).

---

### 2.2 `apply_document_content(target='search')` is not unconditionally safe for headers/footers

**Today**

- `plugin/writer/search.py`: `doc.findFirst` / chaining covers body, tables, frames, and `SwXHeadFootText`. `_header_footer_label` can label `HeaderTextFirst` etc. via `getattr(st, attr, None) == text_obj`.
- `plugin/writer/content.py` `ApplyDocumentContent`: `dry_run` returns locations; `all_matches` replaces every hit; description mentions search as substring find-and-replace but **does not** say matches may be in headers/footers or that first match may be body.
- #634’s refuse message **actively steers** agents to this path as the safe alternative to `page_set`.

**Failure modes**

1. Letterhead firm name also appears in the brief → first replace edits the body.  
2. `all_matches=true` edits header **and** body together.  
3. Searching the field’s rendered `"1"` + replace destroys the field (same as `setString`).  
4. Block HTML into `SwXHeadFootText` inherits nested-`XText` hazards already known for table cells.

**Candidate designs**

| Option | Verdict |
|--------|---------|
| A. Prompt-only: “always dry_run first” | Necessary but **insufficient** — models skip; description still sells unconditional safety |
| B. Require `dry_run` before non-dry search when any match location is header/footer | Better, still document-wide |
| C. Stop pointing header refuse at document-wide search; add **region-scoped** replace on the page tool | **Preferred** |
| D. Add `search_scope=body\|headers\|footers\|all` to `apply_document_content` | Useful later; larger surface than a page-region helper |

**Recommended approach**

- **API shape:** Prefer `page_replace_header_footer_text(style, region, old_content, content, dry_run?)` — one region, one `XText`, optional dry_run that only lists matches **in that region**. This is smaller and more model-friendly than teaching document-wide search discipline.  
- **Honesty:** Change `PageSetHeaderFooterText` refuse text to point at that tool (or “region replace”), not `target='search'`.  
- **Update** `apply_document_content` description: search **can** hit headers/footers; for letterhead wording use the page-region tool; always `dry_run` when unsure; never search field digits.  
- Keep document-wide search for deliberate cross-region edits, with `dry_run` + location strings.

**Tests**

- UNO: body and header both contain `"Acme LLP"`; region replace on `header` changes only header.  
- UNO: `apply_document_content` dry_run reports both locations; first non-dry replace without scope hits body (document the footgun in a test name if we keep the behavior).  
- Unit: refuse message no longer contains `target='search'` as the primary remedy once the page-region tool exists.

**Residual risk**

Until the page-region tool ships, softening refuse-on-fields without a surgical path is unsafe — ship them together or keep field refuse.

---

### 2.3 Region-off leftover content; walk tables

**Today**

```python
# PageSetHeaderFooterText.execute
if style.getPropertyValue(is_on_prop):
    existing = style.getPropertyValue(text_prop)
    if existing:
        scan = _scan_region_content(ctx.doc, existing)
```

`_scan_region_content` only:

- Enumerates **paragraphs → portions** for fields  
- Matches **draw-page shapes** by anchor text  

A letterhead **table** enumerates as a table element, not paragraphs — fields inside cells are missed; `setString` flattens the table.

**Live-verified correction (F5):** on this build `getPropertyValue("HeaderText")` returns **`None`** while `HeaderIsOn=False`, and after an off→on cycle the header is **empty** — plain-text header content is *not* retained across disable. The earlier premise ("LO keeps `HeaderText` when off; re-enable + write deletes it") does **not** reproduce for plain text here. That removes the "always scan when the region is off" work: there is nothing to scan. Re-verify on target LO builds before writing any code for it — do not add an always-scan branch speculatively.

**Recommended approach**

1. **Drop** the "always scan when region off" change (F5). Keep scanning only when the region is on.  
2. On enumeration, if an element is a **table** (or non-paragraph with nested text): either  
   - **refuse** ("region holds a table; use force only to wipe, or edit cells surgically"), or  
   - recursively scan cell `XText`s for fields/images (heavier).  
   Prefer **refuse-on-non-paragraph** for v1 of the follow-up — simple, model-clear, matches "don't flatten structures."  
3. Same rule for text frames nested in the header if encountered.

**Tests**

- UNO: header with 1×2 table → refuse without force; `paragraph_count` / new `structures` signal in scan optional.  
- UNO: plain empty header with region off → set allowed (true empty).  
- (Removed the "logo set off → refuse, content intact when re-enabled" test — the premise did not reproduce; see F5.)

**Residual risk**

Deep nested walks are unbounded; keep caps (`_SCAN_*_LIMIT` already exist) and refuse rather than partial scan false negatives.

---

### 2.4 Header/footer tool still advertises the destructive path

**Today**

`PageSetHeaderFooterText.description` begins: *“Set the text content… Automatically enables…”* Refuse semantics live on the `force` parameter description and in the system prompt.

**Recommended approach**

Rewrite the **description to lead with constraints** (models read this first):

- Plain-text **whole-region** replace.  
- Refuses if the region holds **images or tables** (and, until surgical replace exists, fields).  
- Prefer **region-scoped replace** for wording changes.  
- `force=true` = deliberate wipe.  
- Enabling/auto_height are secondary sentences.

Parameter docs for `force` should not be the only place truth lives.

**Tests**

- Snapshot/unit: description contains refuse / surgical language; does not claim unconditional set.  
- No UNO required.

---

### 2.5 Image identity can miss the logo (`XText` `==` / PyUNO)

**Today**

```python
if shape.getAnchor().getText() != text_obj:
    continue
```

`_header_footer_label` in `search.py` uses the same fragile `getattr(st, attr, None) == text_obj`.

`plugin/draw/shapes.py` `_page_index_for` already documents the robust pattern: `is` → `==` → `uno.isSame` if present.

**Failure mode**

If `!=` is True for the same underlying `XText`, the logo is invisible to the scan → refuse skipped → `setString` deletes the letterhead — **#634’s bug with a false sense of safety**.

**Recommended approach**

Extract a tiny helper, e.g. `uno_text_same(a, b) -> bool`, next to other UNO identity helpers (or in `page.py` shared with search labeling):

1. `a is b`  
2. try `a == b`  
3. try `uno.isSame(a, b)` when available  
4. else False (fail closed for safety scans: if unsure, treat as **match** when scanning for destruction? or fail closed as “held unknown”)

For **refuse scans**, fail closed means: if identity is uncertain, **assume the shape might be in-region** only when ImplementationName/anchor suggests header — actually safer refuse rule: if `getAnchor()` succeeds and `ImplementationName` of text is `SwXHeadFootText` and we can’t prove it’s a *different* region, include it. Simpler practical rule used elsewhere: try all three comparisons; if any says same → same. If all say different → different. The false-negative (miss logo) is the disaster; false-positive (extra refuse) is recoverable with `force`.

Also reuse the helper in `_header_footer_label` so labeling and scanning agree.

**Tests**

- **Live UNO required** (mocks cannot catch this): AS_CHARACTER graphic in header; assert scan lists it; set without force refuses; document unchanged.  
- Unit: helper returns True for mocked equal paths; False when all differ.

**Residual risk**

`uno.isSame` missing on some builds — already handled in shapes.py; copy that comment.

---

### 2.6 First-page letterhead still half-reachable

**Today**

- `_REGION_PROPS` includes `header_first` / `footer_first` → text get/set works when `FirstIsShared=False`.  
- `image_insert` `target` enum is only `body|header|footer`. `insert_image_into_header_footer` keys off the same shared regions.

**Recommended approach**

Extend `target` (and the insert helper) to accept `header_first` / `footer_first`, reusing `_REGION_PROPS` / page helpers already used for text. Update description: first-page logos need `first_is_shared=false` then `target=header_first`.

If extending image insert slips, the page-tool description must **say** image_insert cannot place first-page logos yet — half-reachable without disclosure is the bug.

**Tests**

- UNO: `FirstIsShared=False`, insert into `header_first`, confirm `HeaderText` empty of that graphic and `HeaderTextFirst` holds it.  
- Extend `tests/writer/test_search_reach.py` `FakePageStyle` with `HeaderTextFirst` so label strings don’t regress.

---

### 2.7 Same-style house-font on first `apply_style` (lawyer path)

**Today (`format.py` `apply_paragraph_style_preserving_direct_char`)**

Default `clear_direct="none"` restores all captured Char* overrides → house font invisible; the hint tells the agent to retry with `style_props`.

Initial plan proposal: on default/`none`, if current `ParaStyleName == style_name`, skip restoring only `STYLE_GOVERNED_CHAR_PROPERTIES` (font/size), still restore bold/italic/colour; do not clear `CLEARABLE_PARA_PROPERTIES`.

**Live-verified LO behavior (F1–F3)** — this settles the open questions:

1. Re-applying the **same** `ParaStyleName` **does drop direct Para*** (`ParaLeftMargin` 1500 → 0). A different style does too. So `clear_direct='none'` overclaims “preserves formatting” for indents on *any* re-apply.
2. Char* is **split**, not uniform:
   - **Paragraph-wide** direct Char* (whole-paragraph bold/size) is **reset** by same-style apply.
   - **Portion-level** direct Char* (a bold run) is **preserved** by same-style apply.
   - A portion’s `getPropertyValue("CharWeight")` surfaces a paragraph-wide override (F3), so the capture cannot tell the two apart.

**Assessment:** the plan’s *direction* is right, but “skip restoring font/size” alone is **insufficient**. LO itself preserves portion-level font, so skipping the restore leaves the old font on runs — exactly the common `.docx` case. The same-style path must **actively clear** `STYLE_GOVERNED_CHAR_PROPERTIES` (what `style_props` already does), not merely skip restoring them, while still restoring bold/italic/colour.

**Recommended approach**

On default/`none` with current `ParaStyleName == style_name` (compare against the *resolved*, case-insensitive name — `ApplyStyle` already resolves case-insensitively at `styles.py`):

- skip restoring `STYLE_GOVERNED_CHAR_PROPERTIES`, **and** call `_reset_properties_to_default(capture_cursor, STYLE_GOVERNED_CHAR_PROPERTIES)` so the portion-level font/size LO preserved is cleared and the house font shows.
- still restore bold/italic/colour (portion-level bold is preserved by LO; restoring is a no-op that keeps the red/bold inline tests green).
- do **not** clear `CLEARABLE_PARA_PROPERTIES` (but note LO drops Para* regardless — see the resolved murky item below).

Clarify product semantics:

- Omitted / `"none"` + **same style** → house font wins, emphasis kept; **quote indents are NOT preserved** (LO resets Para*).  
- Omitted / `"none"` + **different style** → today’s full restore (indents still dropped by LO).  
- `"style_props"` / `"all"` unchanged explicit clears.

**Tests** (as plan, plus)

- UNO lawyer sequence → Arial 9.5, bold survives.  
- Existing preserve-inline red/bold still passes.  
- UNO: Standard paragraph with a **portion-level** Times run, same-style house-font apply → the run yields to the house font (proves the active clear, not just skip-restore).  
- Unit: same-style path clears font/size AND does not restore them.

**Residual risk**

Intentional portion-level font (a Courier word inside an already-Standard paragraph) is lost on house-font apply — now because the *active clear* removes it, not because of skip-restore. Accept until evidence says otherwise; document in the tool description one line.

**Murky UNO — RESOLVED (F1):** re-applying the same `ParaStyleName` drops direct Para* (indents/alignment). So either the `none` path must also capture+re-apply Para* (heavier), or the docs/tool description stop promising indent preservation on re-apply. Default to the honest wording (no indent promise) unless a UNO test later demands restore — do **not** paper over this with more prose.

---

### 2.8 `get_string_without_tracked_deletions` paragraph walk

**Today (`plugin/doc/text_helpers.py`)**

Always `createEnumeration()` and treats each child as a **paragraph**, joining with `\n`. On a **paragraph** `XTextRange`, children are **portions** → bold runs become separate “paragraphs” with newlines. `html_export._visible_portions` reimplements the correct portion walk and comments that it must stay aligned for offset paint.

**Live-verified (F4):** `para.createEnumeration()` returns Text portions, and `get_string_without_tracked_deletions(para)` on a single paragraph with one bold run returns `'Paragraph \nwith n\normal and bold text\n'` — a spurious `\n` between every run.

Call sites still passing paragraph-ish objects: `tree.py`, `text_analytics.py`, `linguistic_index.py`, plus html_export’s intentional bypass.

**Recommended approach**

- Detect paragraph (service `com.sun.star.text.Paragraph` or first child has `TextPortionType`).  
- Portion mode: concatenate **without** `\n` (same Redline/Delete rules).  
- Document mode: keep paragraph `\n` join.  
- Move `_visible_portions` beside the helper and reuse — one walk, one error policy (`continue` vs `return` must match; prefer `continue` for robustness unless paint requires abort — paint currently `return`s on portion enum failure to avoid offset drift; document that divergence if kept).

**Tests**

- UNO: single paragraph with bold run → helper returns one line equal to `getString()` visible text (no mid `\n`).  
- UNO: multi-paragraph range still joins with `\n`.  
- Offset paint still matches helper string (existing range-export path).

---

### 2.9 `style_get_info` PageStyles extra hop

**Today (`styles.py`)**

`family == "PageStyles"` returns a tool error telling the agent to call `page_get_style_properties`. Correct functionally; burns a turn.

**Recommended approach**

In-process dispatch to the same implementation `page_get_style_properties` uses (shared function, not a nested LLM call). Return that payload with a clear `family: PageStyles` (or existing page-tool shape). Error redirect was a fine first cut; dispatch is the proper small fix.

**Tests**

- Unit/mock: `style_get_info(PageStyles, Standard)` returns margin/header fields without `status=error`.

---

### 2.10 `data-lo-para` colour / escape / attribute detection

**Today (`xhtml_style_postprocess.py`)**

- `_FODT_OVERRIDE_ATTRS` includes margins, indent, align, line-height, **font-name/size/weight/style** — docstring correctly claims geometry + paragraph-level font.  
- **`fo:color` is absent** — Issue-1-style “center + red” still won’t show red in `data-lo-para` (char-level red may still appear via text-* spans). Docs that claim “colour” in `data-lo-para` are wrong; `llm-styles.md` may still say Para colour not preserved — align claims.  
- Inject: `' data-lo-para="%s"' % para_css` after `_html.unescape` of ODF values — **no `_html.escape(..., quote=True)`** on emit. A `font-family` containing `"` breaks the tag.  
- `_note_read_only_attrs` (`content.py`): `"data-lo-para" in item` substring — body text mentioning the name false-positives.

**Recommended approach**

1. Add `fo:color` → `color` to `_FODT_OVERRIDE_ATTRS` **or** drop colour claims in docs (prefer add — matches Issue 1 fixture).  
2. Escape attribute values on inject (`quote=True`).  
3. Detect the attribute with a small regex / HTML attr parse, not substring.  
4. Update `llm-styles.md` / plan docs to match reality.

**Tests**

- Unit: font name with `"` round-trips into a well-formed attribute.  
- Unit: export with fo:color in FODT autostyle → `color:` in `data-lo-para`.  
- Unit: content body containing the words `data-lo-para` without the attribute → no `ignored_attributes`.

---

### 2.11 `_paint_direct_formatting` aborts Char* if Para* fails

**Today (`html_export.py`)**

Para property copy in try/except; on failure **`return`** before the portion Char* loop. A single refused `Para*` drops the entire reason the temp-doc path exists (bold/indent visibility on range read).

**Recommended approach**

Catch Para* failures, log, **continue** to portion painting. Char* failures already `continue` per portion.

**Tests**

- Unit with stubs: Para copy raises → Char copy still invoked.  
- UNO range read of bold-inside-odd-para still shows emphasis in export when possible.

---

### 2.12 Smaller nits (brief — plan already clear)

| Item | Recommendation |
|------|----------------|
| `CLEARABLE_PARA_PROPERTIES` “cycle” comment | Define once; import; comment is stale (`styles` already imports from `format`) |
| `_COPY_PORTION_LIMIT` silent truncate | Log warning with counts |
| `_merge_reports` last-wins | Schema note or list per-range overrides — don’t invent a new confirm UX yet |
| Asian/Complex in clear but not `REPORTED_CHAR_PROPERTIES` | Add to report **or** stop clearing unreported names on `style_props` — prefer report them |
| `writeragent_api` proxies | Regenerate when page API grows `force` / regions / replace |
| Live UNO suite gap | Still the highest-value work the plan named — mocks don’t catch XText identity or `setPropertiesToDefault` |

---

## 3. Cross-cutting principles

1. **Refuse vs surgical vs force**  
   - **Refuse** = would destroy structure the tool cannot express (images, tables).  
   - **Surgical** = edit text in-region without touching fields/images.  
   - **Force** = explicit wipe, always reported in `deleted`.  
   Never use force as the “normal” retry for wording.

2. **Region-scoped beats document-wide for letterheads**  
   Headers share strings with bodies. A page-region tool is simpler for models than teaching `dry_run` + location discipline on global search.

3. **Tool description honesty**  
   If refuse/surgical is the real contract, the **description** says so first. Parameters and system prompts are backups.

4. **XText identity**  
   One shared `uno_text_same`; fail closed on refuse scans (prefer false refuse over silent delete).

5. **LO same-style vs different-style**  
   Encode LO’s asymmetry in defaults (same-style house font) rather than making agents discover `style_props` by failed visual confirms.

6. **One text walk**  
   Tracked-deletion visibility must be a single helper; exporters paint from the same string.

7. **Read reports ≠ write instructions**  
   `data-lo-para` stays read-only; detect it as an attribute; escape it; don’t pretend colour exists if FODT doesn’t emit it.

8. **Tests lock UNO quirks before behavior changes**  
   Especially: logo identity, field-preserving replace, same-style font clear. (Region-off leftover is closed out — F5; no behavior to lock.)

---

## 4. Recommended follow-up order

Sequenced so UNO tests pin quirks before API behavior shifts:

1. **Shared `uno_text_same` + live UNO: refuse-on-logo still works** (proves scan identity before changing refuse rules).  
2. **Refuse-on-table** (drop the region-off always-scan — F5 says there is nothing to scan); UNO table-refuse test.  
3. **Field policy + `page_replace_header_footer_text` (or equivalent)** in one slice: stop steering to global search; rewrite `page_set` description; UNO field-preserve replace.  
4. **Same-style default house-font** in `apply_paragraph_style_preserving_direct_char` — active-clear font/size (not skip-restore), per F1–F3; lawyer UNO + preserve-inline regression.  
5. **Fix `get_string_without_tracked_deletions`** + share `_visible_portions`; paragraph UNO test (F4).  
6. **`data-lo-para` escape + `fo:color` (or doc fix) + attribute-shaped `_note_read_only_attrs`**.  
7. **`_paint_direct_formatting` don’t abort Char* on Para* failure**.  
8. **`image_insert` + `header_first` / `footer_first`**; search-reach FakePageStyle.  
9. **`style_get_info` → in-process page props**; regenerate scripting proxies as needed.  
10. **Nits pack:** CLEARABLE single source, portion-limit warning, Asian/Complex reporting, docs (`llm-styles.md`).

Parallelizable: (5)–(7) and (8)–(9) after (1)–(3) land, if staffing allows — but do not change field refuse before surgical replace exists.

---

## 5. Non-goals

- Making `data-lo-para` **writable** / round-tripping Para* through HTML import.  
- Boiling the ocean on full header HTML import into `SwXHeadFootText`.  
- Replacing LibreOffice’s same-style Char* persistence with an extension-wide “always Ctrl+M.”  
- Dropping `apply_document_content` search reach into headers (reach is useful; **unscoped** letterhead edits are the problem).  
- Perfect CJK font reporting before the house-font path works for Latin lawyer docs.  
- Rewriting the entire page API surface (`header_right` etc.) — document unshared behavior; don’t block on it.  
- Expedient “always `force`” or “always `style_props`” prompt patches as substitutes for the API shapes above.

---

## Appendix — quick symbol map

| Concern | Primary symbols |
|---------|-----------------|
| Header refuse / scan | `PageSetHeaderFooterText`, `_scan_region_content`, `_describe_region_contents`, `_REGION_PROPS` — `plugin/writer/page.py` |
| Search reach / labels | `find_chained_range`, `_header_footer_label`, `describe_match_location` — `plugin/writer/search.py` |
| Document apply / dry_run | `ApplyDocumentContent` — `plugin/writer/content.py` |
| Style clear / house font | `apply_paragraph_style_preserving_direct_char`, `STYLE_GOVERNED_CHAR_PROPERTIES`, `CLEARABLE_PARA_PROPERTIES` — `plugin/writer/format.py`; `ApplyStyle` — `styles.py` |
| data-lo-para | `_FODT_OVERRIDE_ATTRS`, `_fodt_override_css`, inject in postprocess — `plugin/writer/xhtml_style_postprocess.py`; `_note_read_only_attrs` — `content.py` |
| Tracked deletions | `get_string_without_tracked_deletions` — `plugin/doc/text_helpers.py`; `_visible_portions`, `_paint_direct_formatting` — `html_export.py` |
| Image targets | `ImageInsert`, `insert_image_into_header_footer` — `plugin/writer/images/images.py` |
| XText identity pattern | `_page_index_for` — `plugin/draw/shapes.py` |
