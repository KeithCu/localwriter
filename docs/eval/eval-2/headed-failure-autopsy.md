# Eval-2 headed failure autopsy

**Audience:** Keith / Chief / Scrolly / harness owners  
**Status:** Living harness-debug note (not a KPI scoreboard).  
**Bar:** **Product/task success** first. Oracles are for later benchmarking; a headed “HAPPY” means the deliverable did the job even if a soft oracle is red. Prefer **DO + why**.

Box run artifacts cited below may be untracked locally; paths are under `docs/eval/eval-2/*/runs/` or `docs/eval/eval-2/runs/` on the shared machine.

**Skip:** slot **#7** `writer-headed-template/` (PARKED).

---

## 1. Snapshot (headed product bar)

| # | Sibling | Headed stamp(s) | Product bar | Oracle | Dominant failure class |
|---|---------|-----------------|-------------|--------|------------------------|
| 3 | AFC Population | `runs/20260908-0030-…-retry2` (Gemini) | **HAPPY** (Sample+SSC, S=65 R=2) | PASS | Earlier thrash = fixture/prompt key mismatch (smoothed) |
| 1 | Tenant Retention | `tenant-…/runs/20260908-0121-…` (Gemini) | **HAPPY** (real memo) | FAIL → softened | Oracle false-red (titles in `text:h`, table cells, length) |
| 2 | Cadaver Proposal | `cadaver-…/runs/20260908-2246-…` (Gemini) | **HAPPY** (real proposal + charts) | FAIL → soften PR | Oracle false-red (aliases, Figure/draw:frame, length) |
| 4 | GMP Change Control | `gmp-…/20260909-0103` then `…-0225` (gpt-oss-120b) | 0103 **NOT HAPPY** → 0225 **HAPPY** | 0225 FAIL cite only | **Peer polarity** dump→fill; then product OK |
| 5 | Floorstand Writer→Calc | `writer-calc-peer-write/…/20260909-0323-…` (gpt-oss-120b) | **NOT HAPPY** | FAIL (empty) | **Peer polarity** extract-not-fill + LO crash |
| 6 | Calc-primary | `calc-primary-model/…/20260909-0400-…` (gpt-oss-120b) | **NOT HAPPY** | FAIL (Regions A–G) | **CSV-row dump** into col A + wrong factor + `#NAME?` invented sheet |
| 8 | Draw-primary | — | no headed yet | soft oracle ready | Predicted: title-only canvas / no connectors |
| 9 | Reverse Tenant | — | no headed yet | soft oracle ready | Predicted: invent rates / ignore CBA brief |
| 10 | Long Writer pack | — | no headed yet | soft oracle ready | Predicted: no TOC field / bold-as-heading / no comments |

---

## 2. Cross-cutting finding: peer ask polarity

Two Writer→peer mutation siblings exist. Same machinery (`send_peer_message` / live peer sidebar). Opposite outcomes.

### 2.1 GMP — dump then fill (product recovered)

**`20260909-0103-gpt-oss-120b` (NOT HAPPY)** — tip `172a36b6` (#680-era master)

- Writer peer-asked Draw: *“Please provide the blank Change Control Tracking Form content (all pages) so I can fill it.”*
- Polarity = **dump/research**, not **fill**.
- Form: `filled_fields=0`. Memo ~987 words with risk content; assistant **claimed** form filled (false).
- No UNO thread-violation dialog. ~26+ min to Ready; Save As needed (Ctrl+S missed trial-dir paths).

**`20260909-0225-gpt-oss-120b` (HAPPY)** — tip base `c91f6378` + local `str_bounded` peer-task truncate (not yet the cloud PR)

- Peer ask: *“Please update the Change Control Tracking Form with the following information: … Please enter these details into the appropriate fields of the Change Control Tracking Form. Leave any fields that require unavailable data blank.”*
- Polarity = **fill-not-dump**.
- Form: `filled_fields=9`, `filled_chars=1497`. Memo ~601 words with required sections.
- Oracle only: “memo does not cite the filled change-control form” — **secondary** vs headed happy bar.
- Also needed a private `str_bounded` (not `ascii_bounded`) truncate fix so long peer tasks did not crash Deal — product/plumbing, not oracle.

**Why 0225 worked:** explicit fill instruction + payload of field values in the peer task; Draw treated as write surface.

### 2.2 Floorstand — extract-not-fill (still broken) — DEEPEST

**`writer-calc-peer-write/runs/20260909-0323-gpt-oss-120b` (NOT HAPPY)**

Evidence (`notes.txt`, `thinking_and_tools.md`, `score.txt`, `/workspace/fs-*.png`):

- Tip `891cd670` (#688). Model gpt-oss-120b:nitro, `max_tool_rounds=150`.
- Writer fired `send_peer_message` **3×**. Asks were to **extract** component-by-component cost **JSON** from the **empty** budget scaffold / email trail — e.g. extract breakdown, return JSON array.
- Calc: `get_sheet_summary` / `read_cell_range` on empty Cost Comparison; more extract asks.
- Workbook stayed scaffold: **`nonempty_cells=2`** (titles only).
- Writer email **blank** (`words: 0`).
- LO/OXT **crashed** after peer round (soffice gone); **0** UNO thread violations / PreContractError.
- Oracle FAIL is honest here — empty deliverables — not a false-red.

**Contrast with GMP:** Draw form has obvious blank fields to fill. Calc scaffold looks like a **sheet to read**. Models default to research polarity unless the peer task says **write cells / fill Cost Comparison**.

**Exact peer asks (observer notes):** Writer asked Calc to *“Please extract the component-by-component cost breakdown … Return a JSON array…”* (×3). Calc then `get_sheet_summary` / `read_cell_range` on empty Cost Comparison. ComputerUse saw assistant text about an empty JSON `[]`. Tip `891cd670` (#688); model `openai/gpt-oss-120b:nitro`; `max_tool_rounds=150`; UNO thread violations **0**; soffice died after peer.

**Prompt already says fill** (`prompt_used.txt` / notes): *“The holiday floorstand budget workbook is already open… Fill that workbook.”* and *“Write the draft email in this open Writer document.”* Product still failed — **eval prompt fill language alone is not enough** when `send_peer_message` tasks default to extract/JSON. GMP recovered only when the **peer task** said update/enter-into-fields (0225), not when the Writer prompt alone said fill.

### 2.3 Solutions (DO + why) — peer polarity

Ordered by leverage for Floorstand / future Writer→Calc:

1. **DO — Peer-task polarity examples in product prompts (Calc + Draw)**  
   Teach: when the sibling is an **empty write target**, `send_peer_*` tasks must say **update/fill/write cells** (or Draw fields), not extract/return JSON/dump blank content.  
   **Why:** 0103 vs 0225 is the controlled experiment; Floorstand is the same miss on Calc.

2. **DO — Harness/eval one-liner in Floorstand `prompt.writeragent.txt` only if (1) is not enough**  
   Gold-shaped: “The budget workbook is empty until you fill it; do not ask Calc only to extract costs.”  
   **Why:** eval-2 already remaps deliverable location; a polarity sentence is harness debug, not KPI gaming — but prefer product prompt (1) so all Calc peers benefit.

3. **DO — Peer-tool description / schema hint**  
   `send_peer_message` description: for writable peers, prefer imperative fill tasks; research of siblings stays `document_research`.  
   **Why:** tool messages train harder than eval prompts (AFC lesson).

4. **DO — Soft telemetry in headed notes**  
   Tag peer asks `fill` vs `dump/extract` from keywords; Scrolly notes “polarity MISS” without waiting on oracle.  
   **Why:** Floorstand oracle FAIL is late; polarity is visible mid-run.

5. **Investigate LO crash after peer (Floorstand)**  
   Separate from polarity; may be long peer / nested drain / OXT. Reproduce with a tiny fill peer ask.  
   **Why:** crash ends the run even if polarity is fixed.

6. **Don’t** gate interactive Ready on peer polarity. **Don’t** add gold dollar totals to the product prompt.

---

## 3. Single-doc Writer: Tenant & Cadaver (product OK)

Both Gemini headed drafts were **real product solves**. Oracles failed on extraction/alias brittleness; softens documented elsewhere (#665 / Cadaver soften).

| Issue | Tenant | Cadaver | Product? |
|-------|--------|---------|----------|
| Section titles in `text:h` only | yes | yes | False-red if oracle reads only `text:p` |
| Counts as table cells / `45.0%` | yes | — | False-red |
| Word band slightly over | 1476>1400 | 2505>2500 | Soft |
| Fee / duration aliases | — | Facility Fee; 60–90 min | False-red |
| Graph as `draw:frame` + “Figure” | — | yes | False-red if text-only |

**DO:** keep oracle softens for benchmarking. **Don’t** treat those reds as product misses (Keith: product over oracle).

---

## 4. AFC Population (product OK after smoother)

- Early Gemini thrash: searched GDPVal entity/KRI strings **not in the fixture** (`SMOOTHER_CHANGES.md`).
- After sheet rename `Population` + Legal Entity / KRI remaps: **`20260908-0030-…-retry2` oracle PASS** (S=65 R=2).
- Earlier `20260908-0009` exhausted mid-stream with weak J/K evidence — process/hung-final, not the same as peer polarity.

**DO:** keep smoother changelog so GDPVal-hard criteria can be restored later. Round budget ~150 mattered for polish; pair with error brake if storms return.

---

## 5. Predicted miss modes (no headed yet) — slots 6 / 8 / 9 / 10

From each sibling `notes.md` + soft oracles after #693. Fold real stamps into this section when Scrolly lands runs.

### 6 — Calc-primary (branch profitability) — LANDED NOT HAPPY

**`calc-primary-model/runs/20260909-0400-gpt-oss-120b`** — tip `7a30dcb4`; model `openai/gpt-oss-120b:nitro`; max 150; ~8–10 min; UNO=0 / PreContract=0; WriterAgent **Error** twice then recovered. Shots: `/workspace/calcprim-*.png`.

**What worked (rules out empty-tab / pin):**
- Sheets created: Raw Data + **5** schedules (Income Statement, Monthly Trend, Branch Ranking, Regional Comparison, Efficiency Volume Profitability).
- Oracle: `schedule_sheets: 5`, `formulas: 208`, **`pinned_columns: 0`**, husks 1/243.
- Not the predicted empty-`create_sheet` miss. Not the AFC-style pin miss.

**Product NOT HAPPY — three real miss classes:**

1. **CSV-row dump (dominant / new)** — whole header and even formula rows written as **one comma-joined string in column A** instead of cell-per-column. Visible on Efficiency Volume Profitability (`calcprim-final.png`: `Implementation Headcount Hours…,0,0,0,…` in A4+; B–J empty bordered husks). ODS also has CSV dumps on Income Statement / Monthly Trend / Branch Ranking / Regional Comparison (header lines and `Revenue,=SUMIFS(...),=SUMIFS(...)` as literal text).  
   **Why:** model treated Calc write like pasting a CSV line; schedules look “filled” in chat but are unusable grids.

2. **Wrong factor → `#DIV/0!` (×20 on Branch Ranking)** — ARPU-style formulas divide Revenue by SUMIFS criteria **`"Units"`** instead of fixture account **`Revenue (Units)`** (denom zero / no match). Predicted miss mode confirmed.

3. **`#NAME?` (×20)** — `VLOOKUP(...;'headcount'.a:b;2;0)` references an **invented sheet** `headcount` that does not exist. Related product bug: Sales $/Headcount without a real headcount source tab.

4. **Sparse Regions A–G** — oracle: *missing Regions A–G (found A only)*. Regional Comparison under-filled vs prompt §4.

**Solutions (DO + why):**

1. **DO — Cell/range write teaching (product prompt + tool description)**  
   One cell or rectangular range per write; never dump a CSV/comma row into a single cell. Mid-run: if `get_sheet_summary` sees long comma-joined A-column strings with empty B+, treat as actuation fail and rewrite.  
   **Why:** CSV-dump is the headed happy-bar killer even when sheet count and formula count look OK.

2. **DO — Factor tokens from fixture in teaching / oracle already soft-fails**  
   Denominators must use exact Raw Data account labels (`Revenue (Units)`, Implementation Hours, …) — not shortened `"Units"`.  
   **Why:** `#DIV/0!` ×20 is wrong-factor, not Ready noise.

3. **DO — Ban invented helper sheets** unless `create_sheet` + populate first  
   Headcount for Sales $/Headcount must come from Raw Data headcount accounts (or an explicitly created sheet), never a phantom `headcount` tab.  
   **Why:** `#NAME?` VLOOKUP to missing sheet.

4. **DO — Regional Comparison completeness check in headed notes**  
   Observer tags Region A–G presence before Ready (oracle already fail-closes).  
   **Why:** found A only is a sparse-schedule miss.

5. **Don’t** call this an empty-tab or pin miss. **Don’t** soften Regions A–G away — product package is incomplete. Soft oracle can still keep husk/#DIV thresholds as secondary once grids are real cells.

**Next headed (after product write fix):** re-run same model; expect real multi-column grids, Regions A–G labels, no CSV-in-A, ARPU denom = `Revenue (Units)`.

### 8 — Draw-primary (process map)

- Title-only canvas (<6 shapes).  
- No connectors.  
- PDF habit (prompt remaps to open Draw).  
**Next headed:** paste in **Draw** sidebar; score `get_draw_tree`.

### 9 — Reverse Tenant (Theatre CBA)

- Invent wages; ignore Writer CBA brief.  
- Blank workbook Ready.  
**Next headed:** Calc-primary chat; confirm brief is research-only.

**Watcher (overnight):** calc-primary stamp folded (`20260909-0400`). Still empty: `draw-primary-deliverable/runs/`, `reverse-tenant/runs/`, `long-writer-pack/runs/` (`.gitkeep` only).

### 10 — Long Writer pack

- No TOC field / Contents.  
- Bold Default instead of named Heading styles.  
- No comments.  
**Next headed:** one Writer doc; no peer.

---

## 6. Ordered next experiments

1. **Floorstand polarity retest** (highest product pain) — product peer-prompt/tool description from §2.3 (1)+(3); same model; expect fill peer asks + nonempty Cost Comparison + non-empty email.  
2. **Calc-primary CSV-dump / factor retest** — after cell-write teaching (§5.6); same model; expect multi-column grids, Regions A–G, no comma-joined A cells, ARPU denom `Revenue (Units)`, no phantom `headcount` sheet.  
3. **Tiny peer-fill crash repro** — one `send_peer` that writes 3 cells; see if LO still dies.  
4. **GMP oracle cite soften** (optional) — secondary; product already HAPPY.  
5. **Draw-primary first headed** — Draw-as-product, not form stand-in.  
6. **Reverse Tenant headed** — Calc write + Writer brief read.  
7. **Long Writer headed** — TOC/styles/comments pack.  
8. Keep folding Scrolly stamps into §1 / §5; amend this file or open follow-up PRs.

---

## 7. Non-goals

- Closing GitHub issues from PR keywords.  
- Editing `docs/eval/gdpval/` gold trees.  
- Treating oracle soft fails as product regressions when headed bar is HAPPY.  
- Un-parking #7 in this note.  
- Inventing peer spawn / PDF AcroForm product claims.

---

## Appendix — artifact index

| Sibling | Path |
|---------|------|
| Floorstand | `writer-calc-peer-write/runs/20260909-0323-gpt-oss-120b/` + `/workspace/fs-*.png` |
| GMP | `gmp-change-control-58ac1cc5/runs/20260909-0103-…` and `…-0225-…` + `/workspace/gmp*.png` |
| Tenant | `tenant-retention-ed2bc14c/runs/20260908-0121-…` |
| Cadaver | `cadaver-proposal-61b0946a/runs/20260908-2246-…` |
| AFC | `docs/eval/eval-2/runs/20260908-0030-…` (+ smoother `afc-sample-83d10b06/SMOOTHER_CHANGES.md`) |
| Calc-primary | `calc-primary-model/runs/20260909-0400-gpt-oss-120b/` + `/workspace/calcprim-*.png` |
