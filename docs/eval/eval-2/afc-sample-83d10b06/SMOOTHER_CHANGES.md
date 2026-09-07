# Smoother-path changelog — AFC eval-2 (`83d10b06`)

Eval-2 headed trials (Gemini / Flash) thrashed on exact-string searches
for keys that are **not** cell text in the Population fixture. This file
records every ease-up so we can restore GDPVal-harder criteria later.

This is **not** a product Ready gate. Do **not** edit gold under
[`docs/eval/gdpval/`](../../gdpval/) or
[`prompt.gdpval.txt`](prompt.gdpval.txt).

Restore harder criteria by reversing the rows below (copy wording from
`prompt.gdpval.txt` unless a later note says otherwise).

## 2026-09-07 — Data sheet tab `Sheet1` → `Population`

| Field | Old | New |
|-------|-----|-----|
| Visible data sheet name in `fixtures/Population v2.ods` and `fixtures/Population v2.xlsx` | `Sheet1` | `Population` |

- **Why:** The writer prompt already talks about a spreadsheet titled
  ‘Population’. The open tab was `Sheet1`, so models wasted rounds
  looking for a sheet that did not exist.
- **Left alone:** ODS database-range `__Anonymous_Sheet_DB__0` (name
  unchanged; its target address was retargeted to
  `Population.A1:Population.H1517` so the range still covers the table).
  XLSX has no Anonymous sheet; `_xlnm._FilterDatabase` now points at
  `Population!$A$1:$H$1517`. Internal style names (`PageStyle_Sheet1`)
  and the `xl/worksheets/sheet1.xml` part name were not renamed.
- **Not added:** a prompt line saying the sheet is already named
  Population. The rename is enough.
- **Restore:** rename the data tab back to `Sheet1` (and point the
  filter/database range at `Sheet1` again). Gold GDPVal still uses
  `Sheet1`.

## 2026-09-07 — Step 3 entity bullets → Legal Entity cell text

| Old (GDPVal / previous writer prompt) | New (exact `Legal Entity` cell) |
|---------------------------------------|---------------------------------|
| `CB Cash Italy` | `Willett Bank Rome` (every row is Italy) |
| `CB Correspondent Banking Greece` | `Willett Bank Athens` (every row is Greece; Correspondent Banking stays on the business bullet) |
| `IB Debt Markets Luxembourg` | `Willett Bank Lux` (every row is Luxembourg) |
| `CB Trade Finance Brazil` | `Willett Bank Brazil` (every row is Brazil) |
| `PB EMEA UAE` | `Willett Bank UAE` (every row is UAE; `EMEA` exists as a Sub-Division on this entity) |

- **Why:** None of the CB/IB/PB composite labels appear in the fixture.
  Flash searched those strings and found nothing.
- **Restore:** put the five GDPVal entity lines back from
  `prompt.gdpval.txt`.

## 2026-09-07 — Step 3 metrics `A1` / `C1` → real KRI names

| Old | New (exact `KRIs` cell) |
|-----|-------------------------|
| `A1` | `Terrorist Financing breaches` |
| `C1` | `Proliferation Financing breaches` |

- **Why:** `A1` / `C1` are not KRI labels (and are easy to confuse with
  cell addresses). Both replacement names are present in the sheet.
- **Restore:** `Include metrics A1 and C1, which carry higher risk weightings.`

## 2026-09-07 — Step 3 business bullet `Trade Finance` → `Marine Finance`

| Old | New (exact `Sub-Division` cell) |
|-----|---------------------------------|
| `Trade Finance` | `Marine Finance` |

Correspondent Banking was already a real Sub-Division and is unchanged.

- **Why:** `Trade Finance` is not in the fixture. `Marine Finance` is,
  including on Willett Bank Brazil (the Brazil entity stand-in).
  `Syndicated Lending` is also present (Lux) if a later cut prefers it.
- **Restore:** `Include entries from Trade Finance and Correspondent Banking businesses.`

## Unchanged (do not treat as eased)

- Variance axes: Q2 in H, Q3 in G; `(G−H)/H` into J; flags in K.
- Zero both quarters.
- Cayman Islands / Pakistan / UAE.
- Coverage across all Divisions and sub-Divisions.
- In-workbook deliverables: sheets titled `Sample` and
  `Sample Size Calculation`.
- Sample-size parameters: 90% confidence, 10% tolerable error.
- Gold `prompt.gdpval.txt`, gold rubric, `docs/eval/gdpval/`.
