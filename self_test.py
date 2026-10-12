# -*- coding: utf-8 -*-
"""self_test for free-tier-exhaustion-predictor — inherits scaffold-v2 defenses D1-D4."""
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")  # D3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import free_tier_exhaustion_predictor as mod  # noqa: E402


def run_cli(argv):  # D1
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = mod.main(argv)
            code = 0 if rc is None else rc
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:  # noqa: BLE001
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


CASES = []


def case(name, cat):
    def deco(fn):
        CASES.append((name, cat, fn))
        return fn
    return deco


TMP = tempfile.mkdtemp(prefix="ftep_selftest_")
TODAY = dt.date(2026, 10, 13)


def write_log(name, entries):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8", newline="") as fh:  # D3
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return p


def pts(n, daily=100, start=None, growth=0):
    start = start or (TODAY - dt.timedelta(days=n - 1))
    return [(start + dt.timedelta(days=i), daily + growth * i) for i in range(n)]


# ------------------------------------------------------------------ [A] functional

@case("A01_parse_date_iso", "A")
def t():
    assert mod.parse_date("2026-10-13") == dt.date(2026, 10, 13)

@case("A02_parse_date_slash", "A")
def t():
    assert mod.parse_date("2026/10/13") == dt.date(2026, 10, 13)

@case("A03_parse_date_datetime", "A")
def t():
    assert mod.parse_date("2026-10-13T08:00:00") == dt.date(2026, 10, 13)

@case("A04_aggregate_dedupes_dates", "A")
def t():
    pts_list = mod.aggregate_log([{"date": "2026-10-01", "units": 50},
                                  {"date": "2026-10-01", "units": 25}])
    assert pts_list == [(dt.date(2026, 10, 1), 75)]

@case("A05_aggregate_sorts_unsorted", "A")
def t():
    pts_list = mod.aggregate_log([{"date": "2026-10-03", "units": 1},
                                  {"date": "2026-10-01", "units": 2}])
    assert pts_list[0][0] < pts_list[1][0]

@case("A06_overall_rate_simple", "A")
def t():
    assert mod.overall_rate(pts(10, 100)) == 100.0

@case("A07_trailing_rate_window", "A")
def t():
    p = pts(14, 100)
    p[-1] = (p[-1][0], 500)
    assert mod.trailing_rate(p, 7) > 100

@case("A08_linreg_slope_growth", "A")
def t():
    assert mod.linreg_slope(pts(10, 100, growth=10)) > 0

@case("A09_linreg_flat_zero", "A")
def t():
    assert mod.linreg_slope(pts(10, 100)) == 0.0

@case("A10_predict_remaining_math", "A")
def t():
    r = mod.predict(pts(10, 100), 10000, today=TODAY)
    assert r["consumed"] == 1000 and r["remaining"] == 9000

@case("A11_predict_exhaustion_date_overall", "A")
def t():
    r = mod.predict(pts(10, 100), 2000, today=TODAY)
    assert r["exhaustion"]["overall"] == "2026-10-23"  # 1000 left / 100 per day = 10 inclusive days

@case("A12_predict_not_exhausted_exit_ok", "A")
def t():
    r = mod.predict(pts(5, 10), 100000, today=TODAY)
    assert r["exhausted"] is False

@case("A13_predict_already_exhausted", "A")
def t():
    r = mod.predict(pts(5, 100), 200, today=TODAY)
    assert r["exhausted"] is True and r["remaining"] <= 0

@case("A14_acceleration_detected", "A")
def t():
    r = mod.predict(pts(14, 100, growth=20), 10 ** 7, today=TODAY)
    assert r["accelerating"] is True

@case("A15_stable_not_accelerating", "A")
def t():
    r = mod.predict(pts(14, 100), 10 ** 7, today=TODAY)
    assert r["accelerating"] is False

@case("A16_monthly_reset_date", "A")
def t():
    r = mod.predict(pts(5, 10), 10 ** 6, reset="monthly", today=dt.date(2026, 10, 13))
    assert r["reset_date"] == "2026-11-01" and r["days_to_reset"] == 19

@case("A17_monthly_cap_suggestion", "A")
def t():
    r = mod.predict(pts(5, 10), 10 ** 6, reset="monthly", today=TODAY)
    assert any("cap daily" in s for s in r["suggestions"])

@case("A18_window_spans_estimators", "A")
def t():
    r = mod.predict(pts(10, 100), 1500, today=TODAY)
    w = r["exhaustion_window"]
    assert w[0] <= w[1]

@case("A19_exhaustion_before_reset_flag", "A")
def t():
    r = mod.predict(pts(10, 200), 2500, reset="monthly", today=TODAY)
    assert any("before reset" in s for s in r["suggestions"])

@case("A20_cli_predict_clean", "A")
def t():
    p = write_log("a20.jsonl", [{"date": "2026-10-%02d" % (i + 1), "units": 100} for i in range(5)])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "100000", "--json"])
    assert code == 0 and json.loads(out)["remaining"] == 99500

@case("A21_cli_exhausted_exit1", "A")
def t():
    p = write_log("a21.jsonl", [{"date": "2026-10-01", "units": 500}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "100"])
    assert code == 1 and "exhausted" in out.lower() or "remaining=-400" in out

@case("A22_cli_text_rates_line", "A")
def t():
    p = write_log("a22.jsonl", [{"date": "2026-10-01", "units": 100},
                                {"date": "2026-10-02", "units": 100}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "10000"])
    assert code == 0 and "rates:" in out

@case("A23_days_observed_span", "A")
def t():
    r = mod.predict(pts(10, 100), 10 ** 6, today=TODAY)
    assert r["days_observed"] == 10

@case("A24_zero_usage_never_exhausts", "A")
def t():
    r = mod.predict(pts(5, 0), 1000, today=TODAY)
    assert r["exhaustion"]["overall"] is None

# ------------------------------------------------------------------ [B] exception / CLI contract

@case("B01_cli_no_subcommand_exit2", "B")
def t():
    assert run_cli([])[0] == 2

@case("B02_cli_unknown_subcommand_exit2", "B")
def t():
    assert run_cli(["forecast"])[0] == 2

@case("B03_missing_quota_flag", "B")
def t():
    p = write_log("b03.jsonl", [{"date": "2026-10-01", "units": 1}])
    assert run_cli(["predict", "--log", p])[0] == 2

@case("B04_missing_log_file_exit2", "B")
def t():
    code, _, err = run_cli(["predict", "--log", "ghost.jsonl", "--quota", "10"])
    assert code == 2 and "error" in err

@case("B05_bad_reset_choice_exit2", "B")
def t():
    p = write_log("b05.jsonl", [{"date": "2026-10-01", "units": 1}])
    assert run_cli(["predict", "--log", p, "--quota", "10", "--reset", "weekly"])[0] == 2

@case("B06_unparseable_date_exit2", "B")
def t():
    p = write_log("b06.jsonl", [{"date": "yesterday", "units": 1}])
    code, _, err = run_cli(["predict", "--log", p, "--quota", "10"])
    assert code == 2 and "unparseable" in err

@case("B07_negative_units_exit2", "B")
def t():
    p = write_log("b07.jsonl", [{"date": "2026-10-01", "units": -5}])
    code, _, err = run_cli(["predict", "--log", p, "--quota", "10"])
    assert code == 2 and ">= 0" in err

@case("B08_missing_date_field_exit2", "B")
def t():
    p = write_log("b08.jsonl", [{"units": 5}])
    code, _, err = run_cli(["predict", "--log", p, "--quota", "10"])
    assert code == 2 and "date" in err

@case("B09_units_string_exit2", "B")
def t():
    p = write_log("b09.jsonl", [{"date": "2026-10-01", "units": "many"}])
    assert run_cli(["predict", "--log", p, "--quota", "10"])[0] == 2

@case("B10_invalid_json_line_exit2", "B")
def t():
    p = os.path.join(TMP, "b10.jsonl")
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write("{oops\n")
    code, _, err = run_cli(["predict", "--log", p, "--quota", "10"])
    assert code == 2 and "line 1" in err

@case("B11_entry_not_object_exit2", "B")
def t():
    try:
        mod.aggregate_log(["scalar"])
        assert False
    except mod.PredictError as e:
        assert "not an object" in str(e)

@case("B12_negative_quota_exit2", "B")
def t():
    p = write_log("b12.jsonl", [{"date": "2026-10-01", "units": 1}])
    code, _, err = run_cli(["predict", "--log", p, "--quota", "-1"])
    assert code == 2 and "non-negative" in err

@case("B13_predict_raises_on_bad_quota", "B")
def t():
    try:
        mod.predict(pts(3, 10), None)
        assert False
    except mod.PredictError:
        pass

@case("B14_bool_units_rejected", "B")
def t():
    try:
        mod.aggregate_log([{"date": "2026-10-01", "units": True}])
        assert False
    except mod.PredictError:
        pass

@case("B15_empty_log_runs", "B")
def t():
    r = mod.predict([], 1000, today=TODAY)
    assert r["days_observed"] == 0 and r["exhaustion"]["overall"] is None

@case("B16_json_mode_keys", "B")
def t():
    p = write_log("b16.jsonl", [{"date": "2026-10-01", "units": 10}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1000", "--json"])
    data = json.loads(out)
    assert {"consumed", "quota", "remaining", "rates", "exhaustion", "suggestions"} <= set(data)

@case("B17_help_mentions_extrapolation", "B")
def t():
    code, out, _ = run_cli(["--help"])
    assert code == 0 and "extrapolation" in out

@case("B18_single_point_rate", "B")
def t():
    assert mod.overall_rate([(TODAY, 50)]) == 50.0

@case("B19_linreg_single_point_zero", "B")
def t():
    assert mod.linreg_slope([(TODAY, 50)]) == 0.0

@case("B20_trailing_empty_zero", "B")
def t():
    assert mod.trailing_rate([], 7) == 0.0

# ------------------------------------------------------------------ [C] extreme edge

@case("C01_unicode_date_keys_unaffected", "C")
def t():
    p = write_log("c01.jsonl", [{"date": "2026-10-01", "units": 1, "备注": "中文"}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "100", "--json"])
    assert code == 0

@case("C02_fractional_units", "C")
def t():
    pts_list = mod.aggregate_log([{"date": "2026-10-01", "units": 0.5},
                                  {"date": "2026-10-02", "units": 0.25}])
    assert mod.overall_rate(pts_list) == 0.375

@case("C03_duplicate_dates_aggregated", "C")
def t():
    p = write_log("c03.jsonl", [{"date": "2026-10-01", "units": 10},
                                {"date": "2026-10-01", "units": 20}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1000", "--json"])
    assert json.loads(out)["consumed"] == 30

@case("C04_unsorted_dates_sorted", "C")
def t():
    p = write_log("c04.jsonl", [{"date": "2026-10-05", "units": 1},
                                {"date": "2026-10-01", "units": 1}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1000", "--json"])
    assert json.loads(out)["days_observed"] == 5

@case("C05_future_dates_still_valid", "C")
def t():
    p = write_log("c05.jsonl", [{"date": "2027-01-01", "units": 1}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "100", "--json"])
    assert code == 0

@case("C06_huge_units_no_crash", "C")
def t():
    r = mod.predict(pts(3, 1e12), 1e15, today=TODAY)
    assert r["exhaustion"]["overall"] is not None

@case("C07_growth_rate_simulation_exhausts", "C")
def t():
    r = mod.predict(pts(14, 100, growth=50), 10 ** 6, today=TODAY)
    assert r["exhaustion"]["simulated"] is not None

@case("C08_simulated_horizon_cap", "C")
def t():
    r = mod.predict(pts(3, 1), 10 ** 12, today=TODAY)
    assert r["exhaustion"]["simulated"] is None  # beyond 3650d horizon

@case("C09_stable_exhaustion_window", "C")
def t():
    r = mod.predict(pts(10, 100), 2000, today=TODAY)
    assert r["exhaustion_window"] == ["2026-10-22", "2026-10-23"]  # simulated vs overall off-by-one spans the window

@case("C10_monthly_reset_december_rollover", "C")
def t():
    r = mod.predict(pts(2, 10), 10 ** 6, reset="monthly", today=dt.date(2026, 12, 15))
    assert r["reset_date"] == "2027-01-01"

@case("C11_zero_quota_with_usage", "C")
def t():
    r = mod.predict(pts(2, 10), 0, today=TODAY)
    assert r["exhausted"] is True

@case("C12_crlf_log_file", "C")
def t():
    p = os.path.join(TMP, "c12.jsonl")
    with open(p, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write('{"date": "2026-10-01", "units": 10}\r\n{"date": "2026-10-02", "units": 10}\r\n')
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1000", "--json"])
    assert code == 0 and json.loads(out)["consumed"] == 20

@case("C13_blank_lines_skipped", "C")
def t():
    p = os.path.join(TMP, "c13.jsonl")
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write('\n{"date": "2026-10-01", "units": 10}\n\n')
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1000", "--json"])
    assert code == 0

@case("C14_long_history_1000d_perf", "C")
def t():
    p = write_log("c14.jsonl", [{"date": (TODAY - dt.timedelta(days=999 - i)).isoformat(),
                                 "units": 100 + i} for i in range(1000)])
    import time
    t0 = __import__("time").perf_counter()
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "10**9".replace("**", "0")])
    assert __import__("time").perf_counter() - t0 < 5

@case("C15_trailing7_uses_last_seven_only", "C")
def t():
    p = pts(30, 10)
    p = p[:-7] + [(d, 1000) for d, _ in p[-7:]]
    r = mod.predict(p, 10 ** 5, today=TODAY)
    assert r["rates"]["trailing7"] == 1000.0

@case("C16_exhaustion_date_iso_format", "C")
def t():
    r = mod.predict(pts(5, 100), 400, today=TODAY)
    d = r["exhaustion"]["overall"]
    dt.date.fromisoformat(d)

@case("C17_suggestion_when_exhausted_monthly", "C")
def t():
    r = mod.predict(pts(5, 100), 100, reset="monthly", today=TODAY)
    assert any("already exhausted" in s for s in r["suggestions"])

@case("C18_json_ascii_false_output", "C")
def t():
    p = write_log("c18.jsonl", [{"date": "2026-10-01", "units": 10}])
    code, out, _ = run_cli(["predict", "--log", p, "--quota", "1e5".replace("e5", "00000"), "--json"])
    assert code == 0 and json.loads(out)["quota"] == 100000

@case("C19_date_with_time_suffix", "C")
def t():
    pts_list = mod.aggregate_log([{"date": "2026-10-01 12:30:00", "units": 10}])
    assert pts_list[0][0] == dt.date(2026, 10, 1)

@case("C20_predict_deterministic", "C")
def t():
    a = mod.predict(pts(10, 100), 2000, today=TODAY)
    b = mod.predict(pts(10, 100), 2000, today=TODAY)
    assert a == b

class TestAll(unittest.TestCase):
    pass


def _build():
    for i, (name, cat, fn) in enumerate(CASES):
        def make(f):
            def m(self):
                f()
            return m
        slug = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
        setattr(TestAll, "test_%s_%03d_%s" % (cat, i, slug), make(fn))
_build()


class TestMeta(unittest.TestCase):
    def test_case_count_ge_60(self):
        self.assertGreaterEqual(len(CASES), 60)

    def test_categories_present(self):
        self.assertEqual({c for _, c, _ in CASES}, {"A", "B", "C"})


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    print("SUMMARY: PASS %d/%d" % (total - fails, total))  # D4
    sys.exit(0 if fails == 0 else 1)
