#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""free-tier-exhaustion-predictor — generic rate-extrapolation exhaustion forecast.

Consumes a dated usage log (JSONL of {date, units}), aggregates it, and
extrapolates three independent rate estimators (overall mean, trailing-k
mean, least-squares slope) to project when a fixed quota runs out. Vendor
neutral: only generic 'units' and 'quota'. Pure stdlib.
"""
import argparse
import datetime as dt
import json
import sys

MAX_HORIZON_DAYS = 3650


class PredictError(Exception):
    """Recoverable input error surfaced as exit 2."""


DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")


def parse_date(s):
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    try:
        return dt.datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        raise PredictError("unparseable date %r" % s)


def aggregate_log(lines, default_units=None):
    """Aggregate JSONL usage entries by date. Returns sorted [(date, units)]."""
    if not isinstance(lines, list):
        raise PredictError("usage log must be a list of entries")
    per_day = {}
    for i, entry in enumerate(lines):
        if not isinstance(entry, dict):
            raise PredictError("entry %d is not an object" % i)
        if "date" not in entry:
            raise PredictError("entry %d missing 'date'" % i)
        d = parse_date(entry["date"])
        units = entry.get("units", default_units)
        if not isinstance(units, (int, float)) or isinstance(units, bool):
            raise PredictError("entry %d units must be a number, got %r" % (i, units))
        if units < 0:
            raise PredictError("entry %d units must be >= 0" % i)
        per_day[d] = per_day.get(d, 0.0) + units
    return sorted(per_day.items())


def load_log(path):
    lines = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise PredictError("line %d invalid JSON: %s" % (n, exc))
    return lines


# ------------------------------------------------------------- rate estimators

def overall_rate(points):
    if len(points) < 2:
        return (sum(u for _, u in points) / len(points)) if points else 0.0
    span = ((points[-1][0] - points[0][0]).days + 1) or 1  # inclusive observed days
    return sum(u for _, u in points) / span


def trailing_rate(points, k=7):
    window = points[-k:] if points else []
    if not window:
        return 0.0
    span_days = (window[-1][0] - window[0][0]).days + 1
    return sum(u for _, u in window) / max(span_days, 1)


def linreg_slope(points):
    n = len(points)
    if n < 2:
        return 0.0
    xs = [0] + [(points[i][0] - points[0][0]).days for i in range(1, n)]
    ys = [u for _, u in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def simulate_exhaustion(points, remaining, daily_rate, start_date):
    """Day-by-day projection for a growing-rate model; returns date or None."""
    if remaining <= 0:
        return start_date
    n = len(points)
    base = trailing_rate(points, min(7, max(1, n)))
    slope = linreg_slope(points)
    used = 0.0
    d = start_date
    for day in range(MAX_HORIZON_DAYS + 1):
        rate = max(0.0, base + slope * day)
        used += rate
        if used >= remaining:
            return d + dt.timedelta(days=day)
    return None


# ---------------------------------------------------------------- prediction

def predict(points, quota, reset="none", today=None):
    if quota is None or quota < 0:
        raise PredictError("quota must be a non-negative number")
    points = sorted(points)  # defensive: estimators assume ascending dates
    today = today or dt.date.today()
    consumed = sum(u for _, u in points)
    remaining = quota - consumed
    est = {
        "overall": overall_rate(points),
        "trailing7": trailing_rate(points, 7),
    }
    projections = {}
    for name, rate in est.items():
        if rate <= 0:
            projections[name] = None
        elif remaining <= 0:
            projections[name] = today
        else:
            days = remaining / rate
            if days > MAX_HORIZON_DAYS:
                projections[name] = None  # beyond forecast horizon
            else:
                projections[name] = today + dt.timedelta(days=int(days))
    proj_sim = simulate_exhaustion(points, remaining, est["overall"], today) if points else None
    projections["simulated"] = proj_sim

    dates = [d for d in projections.values() if d is not None]
    acceleration = linreg_slope(points) > est["overall"] * 0.05 if len(points) >= 3 else False

    suggestions = []
    reset_date = None
    days_to_reset = None
    if reset == "monthly":
        if today.month == 12:
            reset_date = dt.date(today.year + 1, 1, 1)
        else:
            reset_date = dt.date(today.year, today.month + 1, 1)
        days_to_reset = (reset_date - today).days
        if remaining > 0:
            daily_cap = remaining / max(days_to_reset, 1)
            suggestions.append("cap daily usage at %.1f units to last until reset %s"
                               % (daily_cap, reset_date.isoformat()))
        else:
            suggestions.append("quota already exhausted; wait for reset %s" % reset_date.isoformat())
    if acceleration:
        suggestions.append("usage is accelerating (linear slope above average); "
                           "recent-7d rate is the safer planning number")
    for name, d in projections.items():
        if d is not None and reset_date is not None and d < reset_date:
            suggestions.append("projected exhaustion %s (%s) lands before reset; "
                               "consider reducing rate or upgrading"
                               % (d.isoformat(), name))
    return {
        "as_of": today.isoformat(),
        "days_observed": (points[-1][0] - points[0][0]).days + 1 if len(points) >= 2 else (1 if points else 0),
        "consumed": consumed,
        "quota": quota,
        "remaining": remaining,
        "exhausted": remaining <= 0,
        "rates": est,
        "exhaustion": {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in projections.items()},
        "exhaustion_window": ([min(dates).isoformat(), max(dates).isoformat()] if dates else None),
        "accelerating": acceleration,
        "reset": reset,
        "reset_date": reset_date.isoformat() if reset_date else None,
        "days_to_reset": days_to_reset,
        "suggestions": suggestions,
    }


# ------------------------------------------------------------------------ CLI

def _cmd_predict(args):
    lines = load_log(args.log)
    points = aggregate_log(lines)
    report = predict(points, args.quota, reset=args.reset)
    report["observations"] = len(points)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("as_of=%s observed_days=%s consumed=%.1f quota=%.1f remaining=%.1f"
              % (report["as_of"], report["days_observed"], report["consumed"],
                 report["quota"], report["remaining"]))
        print("rates: overall=%.2f/day trailing7=%.2f/day"
              % (report["rates"]["overall"], report["rates"]["trailing7"]))
        for name, d in report["exhaustion"].items():
            print("exhaustion[%s]: %s" % (name, d if d else "never (with this estimator)"))
        if report["exhaustion_window"]:
            print("window: %s .. %s" % tuple(report["exhaustion_window"]))
        if report["accelerating"]:
            print("trend: ACCELERATING")
        for s in report["suggestions"]:
            print("suggestion: %s" % s)
    return 0 if not report["exhausted"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="free-tier-exhaustion-predictor",
        description="Vendor-neutral free-tier exhaustion forecast: rate extrapolation "
                    "(overall / trailing-7 / slope simulation) plus downgrade suggestions.")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("predict", help="forecast exhaustion from a usage log")
    p.add_argument("--log", required=True, help="JSONL usage log of {date, units}")
    p.add_argument("--quota", type=float, required=True, help="total quota in units")
    p.add_argument("--reset", choices=("none", "monthly"), default="none")
    p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd != "predict":
        parser.print_help()
        return 2
    try:
        return _cmd_predict(args)
    except (PredictError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
