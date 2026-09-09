# rubric.eval2 — soft Draw-primary outline (stub)

Not a headed oracle. Score the **saved Draw tree** (shapes, text,
connectors), not a Writer memo and not gold-PDF pixels.

## Criteria themes (not brittle regex)

| Theme | Pass idea | Fail closed |
|-------|-----------|-------------|
| Drawing present | `.odg` opens; page has more than a title box | Missing / empty page |
| Structure | Enough labeled nodes for the gold claim (roles or process steps) | One blob; no labels |
| Connectors | Parent/child or flow links exist in the tree | Orphan boxes only |
| Identity | Fixture names appear on shapes (once gold lands) | Invented org / process that contradicts refs |
| Not a Writer stand-in | The Draw file is the product | Only a Writer paragraph describing a chart |
| Husk ban | No `Error:` text in shapes | Ready-empty husk |

Soft / later: exact geometry, z-order, gold PDF string equality.

## Non-goals

- GMP Form-920 `fld_*` fill.
- Impress / `PresentationDocument`.
- A `--score` CLI in this stub.
