"""Test harness for gta6-twitch-ccu-forecast-01.

1. Synthetic cases (hour1 = 50k, 500k, 2M; JSON, CSV and plain formats;
   tiny 500 and huge 8M edge cases): run main.py, validate the output
   (23 lines, hours 2-24, strictly increasing quantiles, >= 100, medians
   smooth, runtime < 8s, deterministic across two runs).
2. Backtest: a plausible past-launch true curve (hour1 anchored, morning
   ramp, evening peak ~2.0x, overnight fall) for hour1 = 500k. Compute
   mean pinball loss on the LOG scale for our forecast vs the house flat
   baseline (median = hour1 every hour, sigma widening 0.15 -> 0.40).
   Pinball on log values, tau in {0.05, 0.25, 0.5, 0.75, 0.95}:
       loss = (log y - log f) * tau            if log y >= log f
            = (log f - log y) * (1 - tau)      otherwise
   Lower is better. A second true curve (peak only 1.3x — a "flop" launch)
   checks we do not lose catastrophically when the shape is wrong.

Usage: python3 test/backtest.py
"""
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = os.path.join(ROOT, "main.py")
TAUS = (0.05, 0.25, 0.5, 0.75, 0.95)

# Plausible true launch-day shape, hours 2..24 (multiplier on hour 1).
TRUE_SHAPE_PEAKY = [0.75, 0.72, 0.72, 0.75, 0.82, 0.95, 1.08, 1.22, 1.35,
                    1.48, 1.60, 1.72, 1.82, 1.90, 1.97, 2.00, 2.00, 1.95,
                    1.85, 1.70, 1.55, 1.40, 1.25]
TRUE_SHAPE_FLOP = [0.85, 0.85, 0.88, 0.92, 0.98, 1.05, 1.12, 1.18, 1.22,
                   1.26, 1.30, 1.30, 1.28, 1.26, 1.24, 1.22, 1.20, 1.18,
                   1.15, 1.12, 1.08, 1.05, 1.00]


def run_case(case_text, name, suffix=".json"):
    case = os.path.join(HERE, "tmp_%s%s" % (name, suffix))
    out = os.path.join(HERE, "tmp_%s.out" % name)
    with open(case, "w") as f:
        f.write(case_text)
    t0 = time.time()
    p = subprocess.run([sys.executable, MAIN, case, out],
                       capture_output=True, text=True, timeout=30)
    dt = time.time() - t0
    if p.returncode != 0:
        print("FAIL %s: rc=%d %s" % (name, p.returncode, p.stderr[-500:]))
        return None, dt
    with open(out) as f:
        doc = json.load(f)
    lines = [[str(r["hour"])] + [str(x) for x in r["q"]]
             for r in doc["hours"]]
    return lines, dt


def validate(lines, name, hour1):
    ok = True
    if len(lines) != 23:
        print("FAIL %s: %d lines, want 23" % (name, len(lines))); ok = False
    medians = []
    for row in lines:
        if len(row) != 6:
            print("FAIL %s: row %r has %d fields" % (name, row, len(row)))
            ok = False; continue
        h = int(row[0]); qs = [int(x) for x in row[1:]]
        if h < 2 or h > 24:
            print("FAIL %s: bad hour %d" % (name, h)); ok = False
        if any(q < 100 for q in qs):
            print("FAIL %s: quantile < 100: %r" % (name, qs)); ok = False
        if not all(qs[i] < qs[i + 1] for i in range(4)):
            print("FAIL %s: quantiles not strictly increasing: %r"
                  % (name, qs)); ok = False
        medians.append(qs[2])
    for i in range(1, len(medians)):
        step = medians[i] / medians[i - 1]
        if not (0.75 < step < 1.35):
            print("FAIL %s: median jump %.2fx between hours %d-%d"
                  % (name, step, i + 1, i + 2)); ok = False
    if ok:
        print("OK   %s: 23 lines, quantiles strictly increasing, "
              "median %.0f -> peak %.0f (%.2fx hour1) -> %.0f"
              % (name, medians[0], max(medians),
                 max(medians) / hour1, medians[-1]))
    return ok


def pinball_log(true_y, qs):
    """Mean pinball loss on log scale over hours x quantiles."""
    tot, n = 0.0, 0
    for h, y in true_y.items():
        ly = math.log(y)
        for tau, f in zip(TAUS, qs[h]):
            lf = math.log(f)
            d = ly - lf
            tot += tau * d if d >= 0 else (1 - tau) * (-d)
            n += 1
    return tot / n


def house_flat(hour1):
    """House baseline: median = hour1 every hour, sigma 0.15 -> 0.40."""
    out = {}
    for i, h in enumerate(range(2, 25)):
        sig = 0.15 + (0.40 - 0.15) * (h - 2) / 22.0
        zs = (-1.6448536269514722, -0.6744897501960817, 0.0,
              0.6744897501960817, 1.6448536269514722)
        out[h] = [max(int(round(hour1 * math.exp(z * sig))), 100)
                  for z in zs]
    return out


def backtest(hour1, true_shape, label):
    true_y = {h: hour1 * true_shape[i]
              for i, h in enumerate(range(2, 25))}
    case = os.path.join(HERE, "tmp_bt.json")
    out = os.path.join(HERE, "tmp_bt.out")
    with open(case, "w") as f:
        json.dump({"hour1_ccu": hour1}, f)
    subprocess.run([sys.executable, MAIN, case, out], check=True,
                   capture_output=True, text=True, timeout=30)
    ours = {}
    with open(out) as f:
        doc = json.load(f)
    for r in doc["hours"]:
        ours[int(r["hour"])] = [int(x) for x in r["q"]]
    l_ours = pinball_log(true_y, ours)
    l_house = pinball_log(true_y, house_flat(hour1))
    print("BACKTEST %-22s hour1=%7d  ours=%.4f  house-flat=%.4f  "
          "improvement=%+.1f%%  %s"
          % (label, hour1, l_ours, l_house,
             100 * (l_house - l_ours) / l_house,
             "BEATS HOUSE" if l_ours < l_house else "LOSES TO HOUSE"))
    return l_ours, l_house


if __name__ == "__main__":
    all_ok = True
    # --- 1. synthetic cases in each accepted format ------------------
    cases = [
        ("json_50k", json.dumps({"hour1_ccu": 50000}), 50000, ".json"),
        ("json_500k", json.dumps({"hour1_ccu": 500000}), 500000, ".json"),
        ("json_2m", json.dumps({"first_hour": 2000000}), 2000000, ".json"),
        ("csv_500k", "500000\n", 500000, ".txt"),
        ("plain_50k", "hour1 50000\n", 50000, ".txt"),
        ("tiny_500", json.dumps({"hour1_ccu": 500}), 500, ".json"),
        ("huge_8m", json.dumps({"hour1_ccu": 8000000}), 8000000, ".json"),
        ("list_500k", json.dumps([500000, 520000, 540000]), 500000, ".json"),
    ]
    for name, text, hour1, suf in cases:
        lines, dt = run_case(text, name, suf)
        if lines is None:
            all_ok = False; continue
        if dt > 8:
            print("FAIL %s: runtime %.2fs > 8s" % (name, dt)); all_ok = False
        all_ok &= validate(lines, name, hour1)
        # Determinism: run again, byte-identical?
        lines2, _ = run_case(text, name, suf)
        if lines2 != lines:
            print("FAIL %s: non-deterministic output" % name); all_ok = False
    # --- 2. backtests -------------------------------------------------
    backtest(500000, TRUE_SHAPE_PEAKY, "peaky launch (peak 2.0x)")
    backtest(50000, TRUE_SHAPE_PEAKY, "peaky launch, small hour1")
    backtest(2000000, TRUE_SHAPE_PEAKY, "peaky launch, big hour1")
    backtest(500000, TRUE_SHAPE_FLOP, "flop launch (peak 1.3x)")
    print("ALL OK" if all_ok else "SOME CHECKS FAILED")
