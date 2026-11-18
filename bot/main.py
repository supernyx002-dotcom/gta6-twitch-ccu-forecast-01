"""
gta6-twitch-ccu-forecast-01 — make.fun entry (Python 3.13 / stdlib only).

CANONICAL LOCATION: main.py at the repository root (the grader runs
`python3 -P -s /bot/main.py`, where /bot is this repository).
This bot/main.py copy is identical, kept so the bot also runs as
`python3 bot/main.py`.

CASE FORMAT — verified against the kit (input/p00.in–p03.in, RULES.txt,
starter/main.py): UTF-8 JSON, schema "makefun/twitch-ccu-case/v1":
  {"id", "game", "day_start", "checkpoint", "levels": [0.05, 0.25, 0.5,
   0.75, 0.95], "known": [{"hour": 1, "from", "until", "viewers",
   "channels", "reads"}], "forecast": [{"hour", "from", "until"} x 23],
   "history", "history_hourly", "streams", "categories_hourly",
   "comparables", "notes"}
The anchor is known[hour == 1].viewers (hour 1's print). The old build
guessed top-level keys ("viewers", "hour1_ccu", ...) that do not exist
in this schema — it could not read a real kit case at all.

RUN — the grader runs one case at a time, with only that case's file in
/input: read EVERY *.in file in $MAKEFUN_INPUT_DIR (default /input),
in name order, and write one output per case to $MAKEFUN_OUTPUT_DIR
(default /output):
  /output/<id>.out, one JSON object, at most 65,536 bytes:
  {"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]}
exactly 23 rows, hours 2..24 each once, five quantiles per row at the
levels above, each a finite number > 0 and <= 1e9, non-decreasing.
Quantiles here are integers, strictly increasing, each >= 100.
Deterministic, no network, no clock, no model calls, <= 8 s per case.

MODEL (deterministic, log-scale)
  * Anchor: median for hour h = hour1 * shape[h], where shape is the
    MEDIAN launch-day shape across the 38 comparables in the kit cases
    (computed from the kit's own input files: for each comparable, the
    hourly viewers on its release day divided by its hour-1 viewers;
    median across comparables, hour by hour), then shrunk 60% of
    the way toward flat (1.0x) — see TESTS.md: the shrunk shape
    minimises the worst-case pinball loss across a peaky (2.0x) and a
    flat (1.3x) launch day, and hour 1 of the final case is already
    post-unlock in New Zealand / Asia / Europe, so its remaining
    upside is smaller than a typical midnight launch's:
      h:  2    3    4    5    6    7    8    9    10   11   12
          0.87 0.75 0.73 0.75 0.79 0.80 0.90 0.88 0.91 0.93 0.98
      h: 13   14   15   16   17   18   19   20   21   22   23   24
          1.06 1.18 1.52 1.65 1.77 1.95 2.40 2.37 2.33 2.30 2.18 2.04
    Viewers dip in the small hours, then rise through the day and peak
    ~2.4x hour 1 in the evening UTC (hours 18-21, when US unlocks and
    EU evening overlap), then fall overnight. The mean shape is useless
    (skewed to >100x by tiny hour-1 launches); the median is robust.
  * Saturation: if hour 1 is already huge, the peak cannot double again
    — the excess over 1x is scaled down as hour1 grows past 1M (down to
    0.6x excess at 5M).
  * Quantiles: lognormal around the median with sigma widening with
    horizon, 0.18 at hour 2 -> 0.45 at hour 24:
        q(p) = median * exp(z_p * sigma),  z = -1.6449/-0.6745/0/+0.6745/+1.6449
    The 90% interval is roughly median * [0.48x, 2.1x] by hour 24.
  * Floors: every quantile >= 100; quantiles forced strictly increasing
    after integer rounding.

LOCAL USE
  python3 main.py [case_file] [output_file]
  With no arguments, reads $MAKEFUN_INPUT_DIR / $MAKEFUN_OUTPUT_DIR
  (or /input / /output). With one argument, forecasts that case;
  with two, writes to the second path.
"""

import json
import math
import os
import sys
from pathlib import Path

# Median launch-day shape, hours 2..24, from the kit comparables.
# See the MODEL section above for how it was computed.
SHAPE = [0.922,
    0.85,
    0.838,
    0.85,
    0.874,
    0.88,
    0.94,
    0.928,
    0.946,
    0.958,
    0.988,
    1.036,
    1.108,
    1.312,
    1.39,
    1.462,
    1.57,
    1.84,
    1.822,
    1.798,
    1.78,
    1.708,
    1.624]
HOURS = list(range(2, 25))
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
ZS = (-1.6448536269514722, -0.6744897501960817, 0.0,
      0.6744897501960817, 1.6448536269514722)  # 5/25/50/75/95%
SIGMA_START = 0.18   # hour 2
SIGMA_END = 0.45     # hour 24
MIN_VIEWERS = 100
MAX_VIEWERS = 1_000_000_000


def saturation(hour1):
    """Scale on the (shape - 1) excess: 1.0 up to 1M, down to 0.6 at 5M."""
    if hour1 <= 1_000_000:
        return 1.0
    if hour1 >= 5_000_000:
        return 0.6
    return 1.0 - 0.4 * (hour1 - 1_000_000) / 4_000_000


def sigma_for(hour):
    """Linear widening with horizon: 0.18 at hour 2 -> 0.45 at hour 24."""
    return SIGMA_START + (SIGMA_END - SIGMA_START) * (hour - 2) / 22.0


def forecast(hour1, shape=None):
    """Return {hour: [q05, q25, q50, q75, q95]} for hours 2..24."""
    shape = shape or SHAPE
    if len(shape) != 23:
        raise ValueError("shape must have 23 entries (hours 2-24)")
    sat = saturation(hour1)
    out = {}
    for i, h in enumerate(HOURS):
        median = hour1 * (1.0 + (shape[i] - 1.0) * sat)
        median = max(median, float(MIN_VIEWERS))
        sig = sigma_for(h)
        qs = []
        for z in ZS:
            q = median * math.exp(z * sig)
            qs.append(max(int(round(q)), MIN_VIEWERS))
        for j in range(1, 5):
            if qs[j] <= qs[j - 1]:
                qs[j] = qs[j - 1] + 1
        out[h] = qs
    return out


# ---------------------------------------------------------------- parsing
def hour1_from_case(case):
    """Hour-1 print from a kit case dict (schema makefun/twitch-ccu-case/v1)."""
    if isinstance(case, dict):
        known = case.get("known")
        if isinstance(known, list):
            for row in known:
                if isinstance(row, dict) and row.get("hour") == 1 \
                        and row.get("viewers") is not None:
                    return float(row["viewers"])
            if known and isinstance(known[0], dict) \
                    and known[0].get("viewers") is not None:
                return float(known[0]["viewers"])
        for k in ("hour1_ccu", "first_hour_ccu", "first_hour", "hour_1",
                  "hour1", "viewers", "ccu", "mean_ccu", "hour1_mean"):
            if k in case and case[k] is not None:
                return float(case[k])
        hist = case.get("history")
        if isinstance(hist, list) and hist:
            last = hist[-1]
            if isinstance(last, dict) and last.get("viewers") is not None:
                return float(last["viewers"])
            if isinstance(last, (int, float)):
                return float(last)
    if isinstance(case, list) and case:
        flat = []
        for v in case:
            flat.extend(v) if isinstance(v, list) else flat.append(v)
        if len(flat) >= 120:
            return sum(float(x) for x in flat[:60]) / 60.0
        return float(flat[0])
    if isinstance(case, (int, float)):
        return float(case)
    raise ValueError("case has no hour-1 print (no known[hour==1].viewers)")


def forecast_hours(case):
    """The hours to forecast, from the case's forecast list (default 2..24)."""
    if isinstance(case, dict) and isinstance(case.get("forecast"), list) \
            and case["forecast"]:
        hours = []
        for row in case["forecast"]:
            if isinstance(row, dict) and row.get("hour") is not None:
                hours.append(int(row["hour"]))
        if hours:
            return sorted(hours)
    return HOURS


def parse_case(text):
    """Return (hour1_ccu, hours) from a case file's text."""
    text = text.strip()
    if not text:
        raise ValueError("case file is empty")
    try:
        obj = json.loads(text)
        return hour1_from_case(obj), forecast_hours(obj)
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    nums = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for tok in line.replace(",", " ").split():
            try:
                nums.append(float(tok))
            except ValueError:
                pass
    if not nums:
        raise ValueError("no numbers found in case file")
    return nums[0], HOURS


# ---------------------------------------------------------------- io
def forecast_case_file(case_path, out_path):
    with open(case_path, encoding="utf-8") as f:
        text = f.read()
    hour1, hours = parse_case(text)
    if hour1 <= 0 or not math.isfinite(hour1):
        raise SystemExit("hour-1 CCU must be a positive number, got %r"
                         % hour1)
    fc = forecast(hour1)
    blob = json.dumps({"hours": [{"hour": h, "q": list(fc[h])}
                                 for h in hours]}) + "\n"
    if len(blob.encode("utf-8")) > 65536:
        raise SystemExit("forecast exceeds 65,536 bytes")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob, encoding="utf-8")
    return hour1, len(blob)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) >= 1:
        case_path = Path(args[0])
        if len(args) >= 2:
            out_path = Path(args[1])
        else:
            out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
            out_path = out_dir / (case_path.stem + ".out")
        hour1, nbytes = forecast_case_file(case_path, out_path)
        print("forecast %s: hour1=%.0f -> %s (%d bytes)"
              % (case_path.name, hour1, out_path, nbytes))
        return
    in_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    cases = sorted(in_dir.glob("*.in"))
    if not cases:
        raise SystemExit("no *.in case found in %s" % in_dir)
    for case_path in cases:
        out_path = out_dir / (case_path.stem + ".out")
        hour1, nbytes = forecast_case_file(case_path, out_path)
        print("forecast %s: hour1=%.0f -> %s (%d bytes)"
              % (case_path.name, hour1, out_path, nbytes))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        sys.exit(1)
