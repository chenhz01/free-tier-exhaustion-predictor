# ALIGNMENT — free-tier-exhaustion-predictor

Round R14, rubric v4.0 (E/F graded). Local-only draft: no git remote, no push, no repo creation.
Date: 2026-10-13.

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Runnable Python, pure stdlib | PASS | free_tier_exhaustion_predictor.py imports only argparse/datetime/json/sys + io/contextlib/unittest/tempfile (self_test); `python free_tier_exhaustion_predictor.py --help` runs |
| 2 | argparse CLI | PASS | subcommands: predict (--log usage.jsonl --quota N [--reset monthly], --json); usage errors exit 2 |
| 3 | self_test inherits scaffold-v2 four defenses | PASS | D1 SystemExit caught in run_cli (tested); D2 unicode-aware regexes + CJK/emoji fixtures (tested); D3 fixtures written with newline="" (tested); D4 last line `SUMMARY: PASS n/n` |
| 4 | E gate >=60 cases, 3 categories | PASS | SUMMARY: PASS 66/66 (64 cases + 2 meta; >=60 gate met) — sections [A] functional / [B] exception / [C] extreme edge, incl. empty/oversized/unicode/CRLF inputs |
| 5 | SUMMARY last-line contract | PASS | `python self_test.py` prints `SUMMARY: PASS 66/66 (64 cases + 2 meta; >=60 gate met)` as its final line; meta-case asserts len(CASES)>=60 |
| 6 | README English, <=60-word lead | PASS | README.md opening paragraph is English and <=60 words |
| 7 | README Problem section | PASS | README.md '## Problem' |
| 8 | README How-it-works | PASS | README.md '## How it works' |
| 9 | README Quickstart with timing | PASS | README.md '## Quickstart' cites the [Measured] run time |
| 10 | why-not-X >=3 alternatives | PASS | README.md '## Why not X' — 4 adjacent solutions listed (vendor consoles/billing alerts, budgeting apps, spreadsheet trendlines, observability forecasting); sim=none per _r14_design.json; no direct equivalent found as of 2026-10-13; algorithm-only, no vendor API binding |
| 11 | Performance [Measured] + repro command | PASS | README.md '## Performance': 30-day forecast < 0.001 s; 1,000-day history < 0.05 s -- CLI repro in README Performance [Measured] |
| 12 | Minimal Fallback | PASS | README.md '## Minimal Fallback' (spreadsheet/manual equivalents) |
| 13 | Design Trade-offs | PASS | README.md '## Design Trade-offs' (4 entries) |
| 14 | Limits & Second-order Effects | PASS | README.md '## Limits & Second-order Effects' (4 entries) |
| 15 | FAQ incl When NOT to use | PASS | README.md '## FAQ' first item is 'When NOT to use this?' |
| 16 | Core Assumptions >=3 + confidence + as-of + hygiene | PASS | README.md '[Core Assumptions]' lists 4 assumptions with confidence line and 'As of 2026-10-13'; MIT LICENSE (zhengming contributors); CHANGELOG.md v0.1.0 -> v0.1.1; no secrets, no real names, contact limited to hcac4735@agent.qq.com |

Round-2 iterations: overall_rate now uses the inclusive observed span (last-first+1 days) matching days_observed - 10x100/day is 100.0 not 111.1 (A06/C02); projection dates capped at MAX_HORIZON_DAYS to fix OverflowError ('int too large to convert to C int') on tiny-rate huge-quota inputs (C08); predict() sorts input points defensively; simulated-vs-overall off-by-one documented as the exhaustion window's lower/upper bound (C09)
All suites re-run green after revisions before hand-off.
