# `--check` Evening Availability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `--check` flag to neptun.py that collects fresh availability, filters for a target time slot in the next N days, and prints results with an appropriate exit code.

**Architecture:** Reuses the existing `AvailabilityCollector` to scrape fresh data into SQLite, then queries the `availability` table for matching slots. Single new function `run_check_mode()` orchestrates the flow. No new DB tables.

**Tech Stack:** Python 3.13, Selenium (via existing infra), SQLite3, argparse

---

### Task 1: Add CLI arguments

**Files:**
- Modify: `neptun.py:2920-2965` (argparse section)
- Modify: `neptun.py:2923-2933` (epilog examples)

**Step 1: Add three new arguments after the `--trends-days` argument (line 2965)**

```python
    parser.add_argument('--check', action='store_true',
                       help='Check availability for a specific time slot (implies --headless)')
    parser.add_argument('--slot', type=str, default='17:30 - 21:00',
                       help='Time slot to check (default: "17:30 - 21:00")')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days ahead to check (default: 7)')
```

**Step 2: Add example to epilog (after line 2933)**

Add this line to the epilog examples:
```
  python neptun.py --check               # Check evening slot availability (next 7 days)
```

**Step 3: Verify syntax**

Run: `uv run python neptun.py --help`
Expected: Shows `--check`, `--slot`, `--days` in help output.

**Step 4: Commit**

```bash
git add neptun.py
git commit -m "feat: add --check, --slot, --days CLI arguments"
```

---

### Task 2: Implement `run_check_mode()` function

**Files:**
- Modify: `neptun.py` — add new function before `main()` (around line 2915, after `load_subscription_codes()`)

**Step 1: Write the `run_check_mode` function**

Place this after `load_subscription_codes()` (line 2912) and before the main entry point comment (line 2914):

```python
def run_check_mode(slot='17:30 - 21:00', days=7, subscription=None, db_path=DB_FILE, verbose=False):
    """
    Check availability for a specific time slot in the next N days.
    Collects fresh data, then queries for matches.
    Returns exit code: SUCCESS if spots found, NO_AVAILABILITY otherwise.
    """
    from datetime import datetime, timedelta

    print(f"\n=== Sauna Evening Check ===")
    print(f"Checking {slot} for next {days} days...\n")

    # Determine subscription
    if subscription:
        codes = [{'code': subscription, 'name': 'CLI'}]
    else:
        codes = load_subscription_codes()
        if not codes:
            print("No subscription codes found. Set NEPTUN_SUBSCRIPTIONS or use -s CODE.")
            return ExitCode.INVALID_SUBSCRIPTION
        codes = [codes[0]]  # Use first subscription only

    # Initialize browser and collect fresh data
    driver = None
    db = None
    logger = None

    try:
        db = DatabaseManager(db_path)
        logger = NeptunLogger(db, verbose=verbose)
        session_id = db.create_session('check', subscription_codes=codes[0]['code'])
        logger.set_session(session_id)

        browser_options = create_browser_options()
        driver = webdriver.Chrome(options=browser_options)

        finder = ElementFinder(driver, logger)
        verifier = StateVerifier(driver, logger, finder)

        collector = AvailabilityCollector(driver, db, logger, finder, verifier)
        collector.set_session(session_id)

        if verbose:
            print(f"Collecting for {codes[0]['name']} ({codes[0]['code']})...")

        collector.collect_all_subscriptions(codes)

    except Exception as e:
        print(f"Collection error: {e}")
        return ExitCode.NETWORK_ERROR

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if db and logger:
            actions, errors = logger.get_stats()
            db.end_session(session_id, ExitCode.SUCCESS, actions, errors)

    # Query collected data for the target slot and date range
    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        conn = db.conn
        cursor = conn.execute(
            """
            SELECT date, spots_available
            FROM availability
            WHERE time_slot LIKE ?
              AND date >= ?
              AND date <= ?
              AND spots_available > 0
            ORDER BY date
            """,
            (f"%{slot}%", today, end_date)
        )
        results = cursor.fetchall()
    except Exception as e:
        print(f"Query error: {e}")
        return ExitCode.UNKNOWN_ERROR
    finally:
        db.close()

    # Print results
    if results:
        print("AVAILABLE:")
        for date_str, spots in results:
            try:
                day_name = datetime.strptime(date_str, '%Y-%m-%d').strftime('%a')
            except ValueError:
                day_name = '???'
            spot_word = 'spot' if spots == 1 else 'spots'
            print(f"  {date_str} ({day_name}) - {spots} {spot_word}")
        return ExitCode.SUCCESS
    else:
        print(f"No availability for {slot} in next {days} days.")
        return ExitCode.NO_AVAILABILITY
```

**Step 2: Verify syntax**

Run: `uv run python -c "import neptun; print('OK')"`
Expected: `OK` (no import errors)

**Step 3: Commit**

```bash
git add neptun.py
git commit -m "feat: implement run_check_mode() for evening availability check"
```

---

### Task 3: Wire `--check` into main()

**Files:**
- Modify: `neptun.py:2967-2984` (main dispatch section)

**Step 1: Add check mode dispatch after the trends handler (after line 2980)**

Insert after the `if args.trends:` block and before `# Collect mode implies headless`:

```python
    if args.check:
        exit_code = run_check_mode(
            slot=args.slot,
            days=args.days,
            subscription=args.subscription,
            db_path=args.db,
            verbose=args.verbose
        )
        sys.exit(exit_code)
```

**Step 2: Smoke test**

Run: `uv run python neptun.py --check --help`
Then: `uv run python neptun.py --check -v` (will attempt real collection — verify it runs)

**Step 3: Commit**

```bash
git add neptun.py
git commit -m "feat: wire --check mode into main dispatch"
```

---

### Task 4: Add Makefile target and update wrapper script

**Files:**
- Modify: `Makefile` — add `check` target
- Modify: `check-availability.sh` — simplify to use `--check`

**Step 1: Add `check` to Makefile .PHONY line (line 1)**

Add `check` to the `.PHONY` list.

**Step 2: Add Makefile target after `trends-weekly` (after line 67)**

```makefile
# Quick check for evening slot
check:
	uv run python neptun.py --check -v
```

**Step 3: Add help text to the Analytics section (after line 21)**

```
	@echo "  make check          - Check evening slot availability (next 7 days)"
```

**Step 4: Simplify `check-availability.sh`**

Replace the entire content with:

```bash
#!/bin/bash
# Check sauna availability for the 17:30-21:00 slot in the next 7 days
cd "$(dirname "$0")"
uv run python neptun.py --check -v
```

**Step 5: Verify**

Run: `make check`
Expected: Runs the check mode end-to-end.

**Step 6: Commit**

```bash
git add Makefile check-availability.sh
git commit -m "feat: add make check target and simplify wrapper script"
```

---

### Task 5: Final verification

**Step 1: Full help check**

Run: `uv run python neptun.py --help`
Verify: `--check`, `--slot`, `--days` all appear correctly.

**Step 2: Dry run with verbose**

Run: `make check`
Verify: Collects data, queries, prints results (or "no availability").

**Step 3: Verify exit codes**

Run: `make check; echo "Exit: $?"`
Verify: Exit code is `0` (found) or `2` (not found).
