# rubric.eval2 — fail-closed Writer proposal oracle

Derived from the **gold prompt + Cadaver Budget fixture**, not by
letter-shifting gold [`rubric_pretty.txt`](rubric_pretty.txt).
Gold is a Microsoft Word file named
`Collaborative Cadaver Program Proposal.docx`. This variant scores the
**saved open Writer proposal** (`.odt` / `.docx`).

Leave [`docs/eval/gdpval/`](../../gdpval/) untouched.

## What is scored

The harness opens the saved trial artifact (`final_proposal.odt`, or
`.docx` if that is what was saved). **Chat Ready / STREAM_DONE is
ignored.** An empty proposal that ended Ready still fails. Do **not**
fail on gold’s hospital typo **Silverview** (prompt is Hope Hospital).

| Check | Source | Fail closed |
|-------|--------|-------------|
| Writer doc present (`.odt` / `.docx`) and body is non-empty | Writer prompt: proposal in this open document | Missing file / unreadable / no extractable text |
| Mini-proposal length (word band 250–3000) | Gold is ~870 words; empty Ready husks are far shorter | `< 250` (Ready-empty) or `> 3000` |
| `Hope Hospital` present | Prompt (not gold’s Silverview) | String missing |
| Four departments named | Prompt + gold rubric | Missing General Surgery, Thoracic Surgery, Otolaryngology, or Orthopedic Surgery |
| Introduction + cost-savings theme | Writer prompt lead-in | Missing introduction or cost/savings wording |
| Graph or 1–4 participation savings | Writer prompt graph request | Missing `graph`/`chart` **and** missing participation 1–4 + `$` |
| Cadaver unit cost **$2,000** (D2) **or** bundled **$3,000** (category rows 2–5) | Fixture `Sheet1` | Neither `2,000`/`2000` nor `3,000`/`3000` |
| Lab fee **$1,000** (D17 `Annual Cadaver Lab Fee`) | Fixture; gold rubric | Missing `1,000`/`1000` |
| Baseline **4 cadavers** | Prompt + fixture C2 | Missing 4-cadaver baseline |
| Exclude **supplies** and **education** | Prompt + fixture categories | Either word missing |
| Ethical / donor-respect section | Writer prompt first required section | Missing donor/respect/maximize-use theme |
| Anatomy: abdomen→GS, thorax→Thoracic, head/neck→ENT, limb→Ortho | Prompt + gold rubric | Any of the four assignments missing |
| Freeze/thaw **10–12** cycles; **3-hour** thawed window | Prompt | Missing 10–12 or 3-hour |
| Complexity durations: simple **30–45** min; standard **1–1.5** hr; complex **2–3** hr | Prompt | Missing a duration band |
| Per-cadaver simple range **40–48** | 4 × 10–12 cycles (gold-hard) | Missing `40` or `48` |
| No mixing complexity | Writer prompt second section | Missing mixing disclaimer |
| Ban empty / Ready-only / `Error:` husks in body | Observed residue on empty trials | Body matches `Error:` / `#DIV/0!` husks or is blank |

Wrong budget analysis fails even if the proposal is well formatted.
An embedded image for the graph is **not** required in v1 if the body
names a graph/chart or states dollar savings at participation levels
1–4. Soft gold checks (exact $13,000 baseline, shared-vs-per-dept lab
fee sermon, 20–36 vs gold’s 20–24 standard) stay optional.

## Fixture cells (cheap)

`Sheet1` (not a Costs tab): cadaver $2,000, shipping $112.50,
preservation $137.50, cremation $750 → **$3,000/cadaver** if the whole
category is used; lab fee $1,000. Oracle accepts either per-cadaver
figure plus the $1,000 fee.

## What this is not

- Not a full gold-rubric grader (embedded chart pixels, fee-sharing
  consistency proofs, overall +5 style).
- Not a product Ready predicate.
- Not a reason to raise the everyday `chatbot.max_tool_rounds` default (15).
  Headed helper still writes **50** for live trials. Schema **max is 200**
  so a trial can temporarily set 80 or 200 in `writeragent.json` without
  being clamped.
- Not a product multi-doc feature: budget stays research-only.

CLI: `scripts/eval_2_cadaver_oracle.py` or
`scripts/eval_2_headed.py --task cadaver-proposal --score`.
