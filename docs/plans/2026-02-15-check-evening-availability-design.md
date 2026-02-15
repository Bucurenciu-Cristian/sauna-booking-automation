# Design: `--check` CLI Flag for Evening Availability

## Problem

Need a daily automated check for 17:30-21:00 sauna availability in the next 7 days, runnable by cron with stdout/exit code output.

## Solution

Add `--check` flag to `neptun.py` that collects fresh data, filters for the target slot, and prints results.

### CLI Interface

```bash
python neptun.py --check                              # defaults: 17:30-21:00, 7 days, first subscription
python neptun.py --check --slot "17:30 - 21:00" --days 7 -s CODE
```

`--check` implies `--headless`.

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--check` | - | Enable check mode |
| `--slot` | `"17:30 - 21:00"` | Time slot to filter for |
| `--days` | `7` | How many days ahead to check |
| `-s` | First code from input.csv | Subscription code |

### Output

```
=== Sauna Evening Check ===
Checking 17:30 - 21:00 for next 7 days...

AVAILABLE:
  2026-02-17 (Mon) - 3 spots
  2026-02-19 (Wed) - 1 spot
```

Or:

```
No availability for 17:30 - 21:00 in next 7 days.
```

### Exit Codes

- `0` (SUCCESS): Spots found
- `2` (NO_AVAILABILITY): No spots in target slot/period

### Implementation

One new function `run_check_mode(slot, days, subscription, db_path)` that:

1. Runs `AvailabilityCollector` for the given subscription (reuses existing infra)
2. Queries `availability` table for matching slot within date range
3. Prints results, returns exit code

### Scope

- New argparse flags: `--check`, `--slot`, `--days`
- New function: `run_check_mode()`
- New Makefile target: `make check`
- Update `check-availability.sh` to use `--check`
- No new DB tables, no notification integrations
