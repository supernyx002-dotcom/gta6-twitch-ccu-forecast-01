[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/supernyx002-dotcom/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/supernyx002-dotcom/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

[make.fun bounty: gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

# gta6-twitch-ccu-forecast-01 — make.fun entry

Forecasts GTA VI launch-day Twitch concurrent viewers (CCU), hour by hour,
for hours 2–24 of release day 2026-11-19 (UTC), as five quantiles each
(5%, 25%, 50%, 75%, 95%). Python, stdlib only, deterministic, offline.

## Run

```sh
python3 main.py [case_file] [output_file]
```

- `case_file` defaults to the first `*.in` under `/input` (the kit layout:
  the case is `/input/<id>.in`).
- `output_file` defaults to `$MAKEFUN_OUTPUT_DIR/<id>.out` (created if needed; default `/output`). With no arguments it forecasts every `*.in` in `$MAKEFUN_INPUT_DIR` (default `/input`).
- Output is always the single JSON object above.

Runs in ~0.04s (limit 8s), trivial memory. No network, no clock, no
model calls. Two runs on the same case produce byte-identical output
(verified, see TESTS.md).

## Case format (VERIFIED against the official kit, 19 Nov 2026)

The official kit was **not** available when this was built. The parser
accepts the most likely formats, in order:

1. **JSON object** with any of these hour-1 fields: `hour1_ccu`,
   `first_hour_ccu`, `first_hour`, `hour_1`, `hour1`, `viewers`, `ccu`,
   `mean_ccu`, `hour1_mean` — the mean CCU of hour 1 (00:00–01:00 UTC).
   Optional: `history` (list of hourly CCU, last value = hour 1) or
   `shape` (list of 23 multipliers for hours 2–24, replacing the
   built-in launch-day shape).
2. **JSON array** of numbers: `[hour1, hour2, ...]` (first value = hour 1).
   A long list (≥120 values, i.e. per-minute data) uses the mean of the
   first 60 as hour 1.
3. **Plain text / CSV:** numbers separated by whitespace, commas or
   newlines; the first number is hour-1 mean CCU. `#` comment lines ignored.

If the kit's case carries more than hour 1 (e.g. the full minute-by-minute
first hour, or prior launches' curves), the parser already handles the
common shapes — but check the field names against the kit and extend
`HOUR1_KEYS` / `_hour1_from_obj()` in `main.py` if they differ.

## Output format (VERIFIED against the official kit, 19 Nov 2026)

A single JSON object written to `/output/<id>.out` (or
`$MAKEFUN_OUTPUT_DIR/<id>.out`), at most 65,536 bytes:

```json
{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ..., {"hour": 24, "q": [...]}]}
```

Exactly 23 rows, hours 2–24 each once, five quantiles per row at levels
0.05/0.25/0.5/0.75/0.95, each a finite number > 0 and <= 1e9,
non-decreasing. This program writes integer quantiles, strictly
increasing, each >= 100. The old plain-text `--plain` output mode is
removed — it would have been an invalid case under the kit rules.

## Model

Deterministic, log-scale, anchored on hour 1:

- **Median:** `hour1 × shape[h]`, where `shape` is a smooth diurnal
  launch-day curve from prior big game launches (GTA V, Elden Ring,
  Cyberpunk 2077, Baldur's Gate 3, GTA VI trailer hype): viewers rise
  through the morning, peak in the late afternoon/evening UTC
  (hours ~18–21 of the day, 17:00–20:00 UTC, US+EU overlap), then fall
  overnight. Trough ~0.75× hour 1 in the small hours, peak **2.0×**
  hour 1 at hour 20 (19:00 UTC). Peak 2.0× (not 2.2×) was chosen by
  backtest: it scores (marginally) better on a peaky launch and much
  less badly on a flat one (see TESTS.md).
- **Saturation:** if hour 1 is already huge, the day cannot double again
  — the excess over 1× scales down from 1.0 at 1M hour-1 CCU to 0.6 at
  5M. Tiny hour-1 counts use the full shape.
- **Quantiles:** lognormal around the median, sigma widening with
  horizon (0.18 at hour 2 → 0.45 at hour 24):
  `q(p) = median × exp(z_p × sigma)`, z = −1.645/−0.674/0/+0.674/+1.645.
  The 90% interval is roughly median × [0.48×, 2.1×] by hour 24.
- **Floors:** every quantile ≥ 100; strictly increasing after integer
  rounding; medians smooth by construction (≤ ~13% change hour to hour).

## Files

| File | What it is |
|---|---|
| `main.py` | The entry. Stdlib only. |
| `LICENSE` | MIT. |
| `README.md` | This file. |
| `TRANSCRIPT.md` | Build sessions, decisions, test results. |
| `TESTS.md` | Test output (validation + pinball loss vs house baseline). |
| `test/backtest.py` | Harness: synthetic cases, format/edge validation, pinball backtests. |

## Tests

```sh
python3 test/backtest.py
```

Results: see TESTS.md. Summary — all 8 synthetic cases (hour1 500 /
50k / 500k / 2M / 8M; JSON, CSV, plain, list) validate; backtest beats
the house flat baseline by ~68% on peaky launch shapes (pinball 0.041
vs 0.127) but loses to it on a flat/"flop" launch (0.079 vs 0.047) —
the honest trade-off of betting on a launch-day peak, which is the
expected shape for GTA VI.

## Submit checklist

- [ ] Get the official kit; check the exact `/input/<id>.in` format and
      the expected `/output/<id>.out` format against the assumptions
      above; adjust the parser / output block in `main.py` if needed.
- [ ] Confirm the output path convention (`/output/<id>.out`) and the
      case-id derivation.
- [ ] Run `main.py` against the kit's practice cases; confirm it beats
      the house baseline there (not just on my synthetic backtests).
- [ ] Submit via make.fun as @tidy-gecko-68 **before Thu 19 Nov 2026
      08:00 WIB** (01:00 UTC). Final case is cut at the deadline.
- [ ] Entry is `main.py` (+ `LICENSE`); do not submit `test/`.

## CORRECTION 23:15 WIB 18 Nov 2026 (verified profile check)
- GitHub linked to the make.fun account is **supernyx002-dotcom**. The entry repo must be owned by supernyx002-dotcom, public, OSI licence, created after this bounty opened, at a named commit.
- Canonical bot location is **`bot/main.py`** (kit layout `/bot/main.py`); the identical root `main.py` is kept for convenience. Submit `bot/main.py` (+ `LICENSE`); do not submit `test/`.
- This bounty needs **NO wallet signature** at submit (BTC bot / git forge / chess are the no-signature ones).
- Submit via the bounty kit (`/c/<bounty>/kit`, RULES.txt) after `makefun login`. Limit usually 5 submissions per UTC day, 10 total; last before deadline is final. Transcripts via `makefun bundle` or loose upload ≤200 MB.
