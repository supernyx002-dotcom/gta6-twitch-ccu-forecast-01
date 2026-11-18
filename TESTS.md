# TESTS — gta6-twitch-ccu-forecast-01

Run: 2026-11-18 ~23:05 WIB, Python 3.12.3, `python3 test/backtest.py`.
Pinball loss is computed on the LOG scale, taus {0.05, 0.25, 0.5, 0.75,
0.95}, averaged over hours 2–24 × 5 quantiles. Lower is better.
House baseline = flat at hour-1 count every hour, sigma widening
0.15 → 0.40 (the spec's house baseline).

## 1. Format / validation cases — all pass

| Case | Input format | hour1 | Result |
|---|---|---|---|
| json_50k | `{"hour1_ccu": 50000}` | 50,000 | OK — median 38,500 → peak 100,000 (2.00×) → 79,000 |
| json_500k | `{"hour1_ccu": 500000}` | 500,000 | OK — median 385,000 → peak 1,000,000 (2.00×) → 790,000 |
| json_2m | `{"first_hour": 2000000}` | 2,000,000 | OK — peak 3,800,000 (1.90×, saturation) |
| csv_500k | `500000` plain | 500,000 | OK — same as json_500k |
| plain_50k | `hour1 50000` | 50,000 | OK — same as json_50k |
| tiny_500 | `{"hour1_ccu": 500}` | 500 | OK — peak 1,000 (2.00×), all quantiles ≥ 100 |
| huge_8m | `{"hour1_ccu": 8000000}` | 8,000,000 | OK — peak 12,800,000 (1.60×, saturation) |
| list_500k | `[500000, 520000, 540000]` | 500,000 | OK — same as json_500k |

Every case: 23 lines (hours 2–24), quantiles strictly increasing, all
≥ 100, medians smooth (no hour-to-hour jump outside 0.75×–1.35×),
byte-identical output across two runs (deterministic), runtime ~0.04s
(limit 8s).

Sample output (hour1 = 500,000):

```
2 267744 318842 360000 406471 484045
3 255104 307430 350000 398465 480196
...
20 568857 839374 1100000 1441550 2127073
...
24 405472 627483 850000 1151426 1781873
```

Edge cases: empty case file → clean `error: case file is empty`,
exit 1 (no traceback). File with no numbers → clean error, exit 1.

## 2. Backtests (pinball loss, log scale)

True curves are plausible launch-day shapes anchored on hour 1
(peaky: morning ramp, evening peak 2.0×, overnight fall; flop:
flat day, peak 1.3×).

| Backtest | hour1 | Ours | House flat | Improvement |
|---|---|---|---|---|
| Peaky launch (peak 2.0×) | 500,000 | **0.0407** | 0.1274 | **+68.0% — beats house** |
| Peaky launch, small hour1 | 50,000 | **0.0407** | 0.1274 | **+68.0% — beats house** |
| Peaky launch, big hour1 | 2,000,000 | **0.0419** | 0.1274 | **+67.1% — beats house** |
| Flop launch (peak 1.3×) | 500,000 | 0.0785 | **0.0469** | −67.4% — loses to house |

The flop row is the honest limitation: this forecast bets on a
launch-day peak. If GTA VI's day were flat, the flat house baseline
would win. GTA VI is the biggest launch in the series' history, so a
peaky day is the expected shape — but the bet is stated here, not hidden.

## 3. Peak-shape tuning (why 2.0×, not 2.2×)

| Peak | sigma end | Peaky loss | Flop loss |
|---|---|---|---|
| 2.2× | 0.45 | 0.0415 | 0.0957 |
| **2.0×** | **0.45** | **0.0408** | **0.0785** |
| 1.9× | 0.45 | 0.0419 | 0.0705 |
| 1.8× | 0.45 | 0.0434 | 0.0629 |
| 2.0× | 0.55 | 0.0458 | 0.0785 |

2.0× with sigma end 0.45 was chosen: (marginally) best on the peaky
shape and materially less bad on the flop than 2.2×. Widening sigma to
0.55 did not help either shape, so sigma stays 0.18 → 0.45.

## CORRECTION 23:15 WIB 18 Nov 2026 — output format fixed to exact spec
Default output is now a single JSON object `{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]}`, exactly 23 rows hours 2–24, 1,433 bytes for the hour1=500k case (limit 65,536), deterministic (byte-identical reruns), runtime 0.036s (limit 8s). Backtest re-run after the fix: ALL OK — peaky launch pinball 0.0407 vs house-flat 0.1274 (+68.0%, beats house) at hour1 50k/500k/2M; flop launch 0.0785 vs 0.0469 (loses — known bet on a peaky launch day). Canonical bot location is now `bot/main.py` (identical root copy kept).

## KIT VERIFICATION 19 Nov 2026 ~01:12 WIB — real kit cases (not assumed)
- **Parser bug found and fixed.** The old parser looked for top-level
  keys (`hour1_ccu`, `viewers`, ...) that do not exist in the kit schema
  (`makefun/twitch-ccu-case/v1`). On a real kit case it raised
  "no hour-1 field" and fell back to plain-number parsing, taking the
  first number in the file (a year / twitch id) as hour 1 — the forecast
  would have been garbage. It also read only the FIRST `*.in` file and
  ignored `$MAKEFUN_INPUT_DIR` / `$MAKEFUN_OUTPUT_DIR`. All three fixed:
  anchor is now `known[hour == 1].viewers`; every `*.in` in
  `$MAKEFUN_INPUT_DIR` (default `/input`) is read in name order and one
  `<id>.out` written per case to `$MAKEFUN_OUTPUT_DIR` (default `/output`).
- **Kit practice cases, all valid** (0.144 s for all 4, limit 8 s/case):
  p00 hour1=23,357 -> p00.out 1,297 bytes; p01 hour1=116,550 -> 1,375
  bytes; p02 hour1=269,517 -> 1,413 bytes; p03 hour1=119,087 -> 1,377
  bytes. Each: exactly 23 rows, hours 2–24, 5 strictly increasing
  integer quantiles, all in (0, 1e9), <= 65,536 bytes. Two full runs
  byte-identical (determinism PASS).
- **Shape re-derived from the kit.** The old SHAPE (peak 2.0x, from
  "GTA V / Elden Ring / ..." — unverified) is replaced by the MEDIAN
  launch-day shape across the 38 comparables in the kit cases
  (hourly viewers on each comparable's release day / its hour-1
  viewers, median per hour): peak 2.40x at hour 19, 2.04x at hour 24.
  The mean shape is unusable (skewed to >100x by tiny hour-1 launches).
  The median shape is then shrunk 60% toward flat (peak 1.84x):
  on the backtest's two synthetic curves the shrunk shape has the best
  worst case (peaky 0.0711, flop 0.0685) vs the pure median (peaky
  0.0737, flop 0.1034) and vs the old 2.0x shape. Hour 1 of the final
  case is already post-unlock in NZ/Asia/Europe, so its remaining
  upside is smaller than a typical midnight launch's — another reason
  not to bet the full 2.4x.
- **Backtest (current code, blended shape)** — pinball on log scale as
  in test/backtest.py, which omits the RULES.txt factor 2, so official
  losses are 2x these numbers; ranking is unaffected:
  peaky launch (peak 2.0x) hour1 50k/500k/2M: 0.0711 / 0.0711 / 0.0728
  vs house-flat 0.1274 (+44% / +44% / +43% — beats house-flat);
  flop launch (peak 1.3x): 0.0685 vs house-flat 0.0469 (loses — the
  entry still bets on a rising day, just less hard than before).
  The "beats house" here is vs the flat baseline, NOT vs the house's
  superbot model entry, which is the real bar for a prize (RULES.txt:
  a prize needs a score better than the best house entry's).
- The pinball numbers in sections 1–3 above (peaky 0.0407 etc.) are from
  the OLD shape and the OLD backtest run; they are superseded by this
  section. The old `--plain` text output mode is removed: default output
  is now the single JSON object the kit requires.
