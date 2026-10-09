# patterns (auto-generated, do not edit)

## sentiment -> next-day SHComp
| date | zt | dt | zb_rate% | max_lb | next_day_SHComp% |
|---|---|---|---|---|---|
| 2026-09-14 | 55 | 16 | 35.3 | 4 | -0.54 |
| 2026-09-15 | 32 | 27 | 42.9 | 5 | +0.71 |
| 2026-09-16 | 89 | 4 | 11.0 | 6 | -0.41 |
| 2026-09-17 | 47 | 1 | 29.9 | 5 | +0.94 |
| 2026-09-18 | 78 | 0 | 24.3 | 4 | — |

sample size: 5 days — too small for statistical significance; accumulate daily.

## hypothesis to test (need >=30 samples)
1. zb_rate >35% (chasing-high loses money) -> next day index weak / zt count down
2. zb_rate <15% + dt <10 -> healthy, trend likely continues
3. max_lb >=6 (sentiment ceiling) -> next day fade risk high

## notes
- this file regenerates on each run; keep raw data (emotion.jsonl, kline) as source of truth
