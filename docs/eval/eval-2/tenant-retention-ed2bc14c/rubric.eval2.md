# rubric.eval2 — fail-closed Writer memo oracle

Derived from the **gold prompt + exit-survey fixture + renewal letter**,
not by letter-shifting gold [`rubric_pretty.txt`](rubric_pretty.txt).
Gold is a Microsoft Word file named `Tenant Rentention Strategy.docx`.
This variant scores the **saved open Writer memo** (`.odt` / `.docx`).

Leave [`docs/eval/gdpval/`](../../gdpval/) untouched.

## What is scored

The harness opens the saved trial artifact (`final_memo.odt`, or `.docx`
if that is what was saved). **Chat Ready / STREAM_DONE is ignored.** An
empty memo that ended Ready still fails. Do **not** fail on the gold
basename typo `Rentention`.

| Check | Source | Fail closed |
|-------|--------|-------------|
| Writer doc present (`.odt` / `.docx`) and body is non-empty | Writer prompt: memo in this open document | Missing file / unreadable / no extractable text |
| ~1–2 pages (word band 180–1800) | Gold + writer prompt “concise, 1-2 page”; 1800 leaves headroom for table-heavy headed memos (~1500 words) | `< 180` (Ready-empty) or `> 1800` |
| `Harborview Flats` and `Stamford` present | Prompt + gold rubric | Either string missing |
| Objective: **+10% retention / 6 months** | Prompt + gold rubric | Missing `10%` or `6 month` |
| Four section themes present | Writer prompt components 1–4. ODT extract includes `text:h` (LibreOffice headings). Titles may be synonyms (`departure reason/categor`, `exit survey/analysis`, `communication plan/template/cadence`, `email draft/timeline`, `community engagement` / `engagement initiative`) | Missing departure analysis, tiered renewal, communication plan, or community engagement |
| Top reason: **rent increase** **9/20 (45%)** | Fixture: 9 of 20 comments; gold rubric | Missing rent-increase theme; missing count (`9/20`, `9 out of 20`, `9 of 20`, **or** digit `9` near the rent theme **and** survey N=`20` somewhere); or missing `45%` / `45.0%` / `45 percent` |
| Top reason: **lack of community / disconnected** **5/20 (25%)** | Fixture: 5 of 20 comments; gold rubric | Missing community/disconnected theme; missing count (`5/20` / `5 out of 20` / `5 of 20`, **or** digit `5` near the community theme **and** survey N=`20`); or missing `25%` / `25.0%` / `25 percent` |
| Early-bird **90d**, standard **60d**, month-to-month **premium** | Writer prompt §2; letter is the current 60-day one-size offer | Missing any of the three tiers |
| Touchpoints **90 / 60 / 30** | Writer prompt §3 | Any of 90, 60, 30 absent |
| **Two** events | Writer prompt §4 | No “two … event(s)” wording |
| Ban empty / Ready-only / `Error:` husks in body | Observed residue on empty trials | Body matches `Error:` / `#DIV/0!` husks or is blank |

Wrong survey analysis fails even if the memo is well formatted. Web
examples for events are allowed; the oracle does **not** require
specific external citations.

LLM-judge / tone / cost-offset tactics are **out of v1**. Soft checks
in gold `rubric_pretty.txt` stay optional.

## Renewal-letter alignment (cheap)

The staged letter is a single 60-day “take it or leave it” offer.
The memo must introduce 90-day early-bird and month-to-month premium
tiers (table above). No extra one-size-fits-all sermon is required.

## What this is not

- Not a full gold-rubric grader (email subject-line drafts, quantifiable
  incentive math, vendor cost-offset, overall +5 style).
- Not a product Ready predicate.
- Not a reason to raise the everyday `chatbot.max_tool_rounds` default (15).
  Headed helper still writes **50** for live trials. Schema **max is 200**
  so a trial can temporarily set 80 or 200 in `writeragent.json` without
  being clamped.

CLI: `scripts/eval_2_tenant_oracle.py` or
`scripts/eval_2_headed.py --task tenant-retention --score`.
