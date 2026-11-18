# TRANSCRIPT — gta6-twitch-ccu-forecast-01

Build date: 2026-11-18 ~23:05–23:15 WIB. Builder: subagent (Mas Owi).
Account: @tidy-gecko-68. Nothing submitted, signed, or pushed.

## Session 1 — build + test + tune (~23:10 WIB)

1. Wrote `main.py` (Python stdlib only): reads a case (JSON object/array
   or plain numbers/CSV), forecasts hours 2–24 as five lognormal
   quantiles around an hour-1-anchored diurnal shape, writes
   `/output/<id>.out` (or the path given on the command line).
   Parser accepts the hour-1 field under 9 likely key names, a `history`
   list, a `shape` override, per-minute lists, and plain numbers.
2. Wrote `test/backtest.py`: 8 synthetic format/edge cases, determinism
   check, runtime check, and pinball-loss backtests vs the house flat
   baseline on peaky and flop true curves.
3. First run: all format checks passed; peaky backtests beat house by
   ~67–68%, but the flop backtest lost by 104% (peak 2.2× over-predicts
   a flat day badly).
4. Swept the peak multiplier (2.2/2.0/1.9/1.8) and sigma end (0.45/0.55):
   2.0× + sigma 0.45 was (marginally) best on peaky and much less bad on
   flop. Rescaled SHAPE to peak 2.0× and re-ran: peaky +68.0%/+68.0%/
   +67.1%, flop −67.4%.
5. Cleaned up error handling: bad/empty case files now exit 1 with a
   one-line `error:` message instead of a traceback.

## Decisions (and why)

- **Bet on a peaky launch day.** The forecast's edge over the flat
  house baseline comes entirely from the diurnal shape. If GTA VI's day
  were flat, this entry loses to the house baseline — stated in TESTS.md
  rather than hidden. For the biggest game launch ever, peaky is the
  right bet, and 2.0× (not 2.2×) limits the damage if it is flatter
  than expected.
- **Lognormal quantiles, sigma widening 0.18 → 0.45.** Matches the
  spec's scoring (pinball on log scale) and the house's own widening
  spread, with a wider end-sigma than the house (0.45 vs 0.40) to cover
  shape uncertainty.
- **Saturation for huge hour-1 counts.** A launch already doing 8M CCU
  in hour 1 cannot double again the same day; the excess is scaled
  down (peak 1.60× at 8M vs 2.00× at ≤1M).
- **Plain-text output by default, `--json` available.** The kit's exact
  output format is unknown; space-separated `hour q05 q25 q50 q75 q95`
  is the simplest machine-readable layout, and the JSON option is one
  flag away if the kit wants JSON lines.

## Kit verification session, 19 Nov 2026 ~01:11–01:13 WIB
1. Extracted the official kit; read RULES.txt, input/p00.in–p03.in and
   starter/main.py. Found the parser could not read a real kit case
   (wrong hour-1 keys, first-file-only, env dirs ignored).
2. Rewrote the parser for schema makefun/twitch-ccu-case/v1
   (known[hour==1].viewers, forecast hours from the case), multi-case
   input/output via $MAKEFUN_INPUT_DIR / $MAKEFUN_OUTPUT_DIR, single
   JSON {"hours": [...]} output; removed the --plain text mode.
3. Re-derived the shape from the kit: median launch-day shape across
   the 38 comparables in the practice cases (peak 2.40x, hour 19),
   then shrunk 60% toward flat (peak 1.84x) after the blend test showed
   it minimises the worst-case pinball across a peaky and a flat day.
4. Verified on all 4 kit practice cases: valid format, correct anchors,
   0.144 s total, byte-identical reruns. Backtest: peaky 0.0711 vs
   house-flat 0.1274; flop 0.0685 vs 0.0469 (see TESTS.md).
