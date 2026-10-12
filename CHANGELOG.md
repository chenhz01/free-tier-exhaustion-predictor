# Changelog

All notable changes to this project are documented here.
Format based on Keep a Changelog; versioning: SemVer.

## [0.1.1] - 2026-10-13

### Fixed / Revised (round-2 iteration)
- overall_rate now uses the inclusive observed span (last-first+1 days) matching days_observed - 10x100/day is 100.0 not 111.1 (A06/C02)
- projection dates capped at MAX_HORIZON_DAYS to fix OverflowError ('int too large to convert to C int') on tiny-rate huge-quota inputs (C08)
- predict() sorts input points defensively; simulated-vs-overall off-by-one documented as the exhaustion window's lower/upper bound (C09)

### Verification
- self_test re-run green after revisions: SUMMARY: PASS 66/66 (64 cases + 2 meta; >=60 gate met)
- CLI error contract re-verified (exit 0/1/2); four scaffold-v2 defenses inherited.

## [0.1.0] - 2026-10-13

### Added
- Core module `free_tier_exhaustion_predictor.py`: predict (--log usage.jsonl --quota N [--reset monthly], --json), pure standard library.
- argparse CLI with `--json` machine output and 0/1/2 exit-code contract.
- `self_test.py` inheriting scaffold-v2 defenses: SystemExit capture, unicode-safe
  regexes, `newline=""` fixtures, and the `SUMMARY: PASS n/n` last-line contract.
- README (Performance section with [Measured] numbers and in-repo repro commands),
  MIT LICENSE, ALIGNMENT.md (16-item rubric).
