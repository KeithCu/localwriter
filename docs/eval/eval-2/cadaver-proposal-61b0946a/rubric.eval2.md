# rubric.eval2 — fail-closed Writer proposal oracle (v1)

Eliyezer-locked structural checks. Derived from the **gold rubric +
Cadaver Budget fixture**, not by letter-shifting Tenant/AFC.
Gold is a Microsoft Word file named
`Collaborative Cadaver Program Proposal.docx`. This variant scores the
**saved open Writer proposal** (`.odt` / `.docx`). Do **not** fail on
Word vs ODT.

Leave [`docs/eval/gdpval/`](../../gdpval/) untouched.

## What is scored

The harness opens the saved trial artifact (`final_proposal.odt`, or
`.docx` if that is what was saved). **Chat Ready / STREAM_DONE is
ignored.** An empty proposal that ended Ready still fails. Extract
ODT `text:h` and `text:p` (document order), plus DOCX paragraphs
(headings are `w:p`).

| # | Check | Source | Fail closed |
|---|--------|--------|-------------|
| 1 | Writer doc present; body non-empty; word band **250–2500** (tune after first headed) | Mini proposal; Ready-empty husks are far shorter | Missing / unreadable / no text; `< 250` or `> 2500` |
| 2 | Title theme **Collaborative Cadaver Program** (Proposal) | Gold name + writer prompt | Missing that program name |
| 3 | Four departments named | Prompt + gold rubric | Missing General Surgery, Thoracic Surgery, Otolaryngology, or Orthopedic Surgery |
| 4 | Intro / cost-savings purpose **first** | Writer prompt: start with intro + highlight cost savings | Missing introduction or cost-savings, or ethics/anatomy appears before cost-savings |
| 5 | Cost inputs: per-cadaver **Cadaver** + **Annual Cadaver Lab Fee**; **excludes Supplies and Education** (must say exclude) | Fixture line items; gold rubric | Missing per-cadaver / lab-fee names, or no exclude + supplies + education |
| 6 | Baseline **4 cadavers/year** General Surgery; formula **(4 × per-cadaver) + lab fee** | Prompt C2=4; gold rubric | Missing 4-cadaver/year baseline or the formula shape |
| 7 | Savings vs **1–4** departments; **graph or** a clearly labeled savings table | Writer prompt graph | Missing graph/chart **and** missing labeled 1–4 savings table |
| 8 | Ethical maximize-use / honor donors | Writer prompt first required section | Missing donor / honor / maximize-use theme |
| 9 | Anatomy: abdomen→Gen Surg, thorax→Thoracic, head/neck→Oto, limb(s)→Ortho | Gold rubric | Any of the four assignments missing |
| 10 | Constraints: **10–12** freeze/thaw; **3h** thawed; simple **30–45m** / standard **1–1.5h** / complex **2–3h**; per window simple **≤4**, standard **2–3**, complex **1**; totals simple **40–48**, standard **20–36**, complex **10–12** | Prompt + gold rubric | Any band missing |
| 11 | Explicit **no mixing** complexities | Writer prompt second section | Missing mixing disclaimer |
| 12 | Ban empty / Ready-only / `Error:` husks | Observed residue | Body matches `Error:` / `#DIV/0!` husks or is blank |

Wrong analysis of the locked bands fails even if the proposal is well
formatted. An embedded chart image is **not** required in v1.

## Soft / later (not v1)

Exact dollar figures, how the lab fee is shared, per-department
procedure ranges, and chart aesthetics. Gold’s **Silverview** hospital
name is not a scored string. Do not fail on `.docx` vs `.odt`.

## Non-goals

- Editing the budget workbook (research / read-only).
- Dual deliverables / a second writable document.
- Product multi-doc feature work.
- A full gold-rubric grader or a product Ready predicate.
- Raising the everyday `chatbot.max_tool_rounds` default (15). Headed
  helper still writes **50**. Schema **max is 200**.

CLI: `scripts/eval_2_cadaver_oracle.py` or
`scripts/eval_2_headed.py --task cadaver-proposal --score`.
