# Neptune HTTP Rewrite

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite neptun.py from scratch as a fast HTTP-only CLI that replaces all Selenium interactions with direct HTTP requests, keeping SQLite logging and adding an interactive book-after-check flow.

**Architecture:** Single file `neptun.py` (~400 lines). A `BPSBClient` class wraps all HTTP interactions. CLI uses argparse with subcommands. The interactive flow is: check availability → display results → prompt to book. No browser needed.

**Tech Stack:** Python 3.13, requests, sqlite3, argparse, dotenv

**Reference:** `docs/api-discovery.md` for all endpoints and payloads.

---

### Task 1: Scaffold the new file with config and exit codes

**Files:**
- Create: `neptun_fast.py` (new file, will replace `neptun.py` later)

**Step 1: Write the skeleton**

```python
"""Neptune — Fast sauna booking CLI (HTTP-only, no browser)."""
import argparse
import os
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://bpsb.registo.ro"
BOOKING_URL = f"{BASE_URL}/client-interface/appointment-subscription"
DB_FILE = "neptun.db"


class ExitCode:
    SUCCESS = 0
    INVALID_SUBSCRIPTION = 1
    NO_AVAILABILITY = 2
    BOOKING_FAILED = 3
    NETWORK_ERROR = 4
    UNKNOWN_ERROR = 99
```

**Step 2: Verify syntax**

Run: `uv run python -c "import neptun_fast; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: scaffold neptun_fast.py with config and exit codes"
```

---

### Task 2: BPSBClient — session setup and subscription validation

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add BPSBClient class with init_booking_session**

```python
class BPSBClient:
    """HTTP client for BPSB booking system."""

    def __init__(self, verbose=False):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        self.verbose = verbose
        self.subscription_id = None
        self.resource_id = None

    def log(self, msg):
        if self.verbose:
            print(f"  {msg}")

    def init_booking_session(self, subscription_code):
        """Walk steps 1-3 to establish a booking session. Returns date constraints."""
        # Step 1: establish PHP session
        self.session.get(f"{BOOKING_URL}/step1", timeout=15)

        # Step 2: submit subscription code
        r2 = self.session.post(f"{BOOKING_URL}/step2",
                               data={"clientInput": subscription_code}, timeout=15)
        r2.raise_for_status()

        sub_match = re.search(r'name="subscription"\s+value="(\d+)"', r2.text)
        res_match = re.search(r'name="resource"\s+value="(\d+)"', r2.text)
        if not sub_match or not res_match:
            return None

        self.subscription_id = sub_match.group(1)
        self.resource_id = res_match.group(1)

        # Step 3: select sauna resource
        r3 = self.session.post(f"{BOOKING_URL}/step3",
                               data={"resource": self.resource_id,
                                     "subscription": self.subscription_id}, timeout=15)
        r3.raise_for_status()

        return self._parse_date_constraints(r3.text)

    def _parse_date_constraints(self, html):
        """Extract datepicker config from step3 JS."""
        constraints = {"disabled_dow": set(), "blackout_dates": set(),
                       "max_date": None}

        dow_match = re.search(r'daysOfWeekDisabled:\s*"([\d,]+)"', html)
        if dow_match:
            constraints["disabled_dow"] = {int(d) for d in dow_match.group(1).split(",")}

        constraints["blackout_dates"] = set(
            re.findall(r'e\.format\(\)=="(\d{4}-\d{2}-\d{2})"', html)
        )

        val_end = re.search(r'var valabilityEnd\s*=\s*moment\("(\d{4}-\d{2}-\d{2})"\)', html)
        if val_end:
            end = datetime.strptime(val_end.group(1), "%Y-%m-%d")
            constraints["max_date"] = min(end, datetime.now() + timedelta(days=30))

        return constraints
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import BPSBClient; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add BPSBClient with session setup and subscription validation"
```

---

### Task 3: BPSBClient — get_slots and book

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add get_slots_for_date and book_slot methods**

```python
    def get_slots_for_date(self, date_str):
        """Get available slots for a date. Returns list of {time, spots, interval_id}."""
        r = self.session.post(f"{BOOKING_URL}/step4",
                              data={"date": date_str}, timeout=15)

        slots = []
        # Each slot has a form with interval ID and nearby text with time + spots
        forms = re.findall(
            r'<h5[^>]*>(.*?)</h5>.*?'
            r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}).*?'
            r'Locuri disponibile:\s*(\d+).*?'
            r'name="interval"\s+value="(\d+)"',
            r.text, re.DOTALL
        )
        for _, time_str, spots, interval_id in forms:
            slots.append({
                "time": time_str.strip(),
                "spots": int(spots),
                "interval_id": interval_id,
            })

        # Fallback: parse time and spots separately if structured parsing misses
        if not slots:
            times = re.findall(r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})', r.text)
            spots_list = re.findall(r'Locuri disponibile:\s*(\d+)', r.text)
            intervals = re.findall(r'name="interval"\s+value="(\d+)"', r.text)
            for i in range(min(len(times), len(spots_list), len(intervals))):
                slots.append({
                    "time": times[i].strip(),
                    "spots": int(spots_list[i]),
                    "interval_id": intervals[i],
                })

        return slots

    def book_slot(self, interval_id):
        """Book a slot by interval ID. Returns True on success."""
        r = self.session.post(f"{BOOKING_URL}/register",
                              data={"interval": interval_id}, timeout=15)
        r.raise_for_status()
        # Check for success indicators in response
        # The register endpoint redirects or shows confirmation
        return r.status_code == 200
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import BPSBClient; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add get_slots_for_date and book_slot to BPSBClient"
```

---

### Task 4: BPSBClient — auth flow (login, appointments, delete)

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add auth methods**

```python
    def login(self, email, password):
        """Login to BPSB. Returns True on success."""
        # Load login page to get CSRF token
        r = self.session.get(f"{BASE_URL}/login", timeout=15)
        csrf = re.search(r'name="_csrf_token"\s+value="([^"]+)"', r.text)
        if not csrf:
            return False

        r = self.session.post(f"{BASE_URL}/login_check", data={
            "_csrf_token": csrf.group(1),
            "_username": email,
            "_password": password,
            "_submit": "Autentificare",
        }, timeout=15)

        return "/login" not in r.url

    def get_appointments(self):
        """Get current appointments. Returns list of dicts. Must be logged in."""
        r = self.session.get(f"{BASE_URL}/client-user/appointments", timeout=15)
        if "/login" in r.url:
            return None  # Not logged in

        appointments = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 5:
                continue
            clean = lambda s: re.sub(r'<[^>]+>', ' ', s).strip()
            delete_match = re.search(r'data-id="([^"]+)"', row)
            appointments.append({
                "resource": clean(cells[1]),
                "datetime": clean(cells[2]),
                "places": clean(cells[3]),
                "price": clean(cells[4]),
                "delete_id": delete_match.group(1) if delete_match else None,
            })
        return appointments

    def delete_appointment(self, delete_id):
        """Delete an appointment by its ID. Returns True on success."""
        r = self.session.get(f"{BASE_URL}/appointment/delete/{delete_id}", timeout=15)
        try:
            data = r.json()
            return True
        except Exception:
            return r.status_code == 200
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import BPSBClient; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add login, get_appointments, delete_appointment to BPSBClient"
```

---

### Task 5: Database manager (minimal)

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add lightweight DB class**

Reuse the existing schema from the old `neptun.py` but stripped to essentials.

```python
class DB:
    """Minimal SQLite logger for availability tracking."""

    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                subscription_code TEXT,
                date TEXT,
                time_slot TEXT,
                spots_available INTEGER,
                session_id TEXT
            )
        """)
        self.conn.commit()

    def log_slot(self, session_id, code, date, time_slot, spots):
        self.conn.execute(
            "INSERT INTO availability (session_id, subscription_code, date, time_slot, spots_available) VALUES (?, ?, ?, ?, ?)",
            (session_id, code, date, time_slot, spots),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import DB; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add minimal DB class for availability logging"
```

---

### Task 6: Subscription loading from env

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add helpers for loading config**

```python
def load_subscriptions():
    """Load subscription codes from NEPTUN_SUBSCRIPTIONS env var."""
    raw = os.getenv("NEPTUN_SUBSCRIPTIONS", "")
    codes = []
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            code, name = pair.split(":", 1)
            codes.append({"code": code.strip(), "name": name.strip()})
    return codes


def get_credentials():
    """Load login credentials from env."""
    email = os.getenv("NEPTUN_EMAIL")
    password = os.getenv("NEPTUN_PASSWORD")
    if email and password:
        return {"email": email, "password": password}
    return None


def candidate_dates(constraints, days):
    """Generate bookable dates for the next N days respecting constraints."""
    today = datetime.now()
    end = today + timedelta(days=days)
    if constraints.get("max_date"):
        end = min(end, constraints["max_date"])

    dates = []
    d = today
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        js_dow = (d.weekday() + 1) % 7  # Python Mon=0 → JS Sun=0
        if js_dow not in constraints.get("disabled_dow", set()) and ds not in constraints.get("blackout_dates", set()):
            dates.append(ds)
        d += timedelta(days=1)
    return dates
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import load_subscriptions, candidate_dates; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add subscription loading and date generation helpers"
```

---

### Task 7: `check` command — check availability and optionally book

This is the core interactive flow: scan → display → prompt → book.

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add cmd_check function**

```python
def cmd_check(args):
    """Check availability, display results, optionally book."""
    t_start = time.time()
    sub = _resolve_subscription(args.subscription)
    if not sub:
        return ExitCode.INVALID_SUBSCRIPTION

    client = BPSBClient(verbose=args.verbose)
    constraints = client.init_booking_session(sub["code"])
    if not constraints:
        print(f"Invalid subscription: {sub['code']}")
        return ExitCode.INVALID_SUBSCRIPTION

    dates = candidate_dates(constraints, args.days)
    client.log(f"Checking {len(dates)} dates for {sub['name']}...")

    # Collect all slots
    db = DB(args.db)
    session_id = str(uuid.uuid4())[:8]
    all_results = []  # [(date, time, spots, interval_id)]

    for date_str in dates:
        slots = client.get_slots_for_date(date_str)
        for s in slots:
            db.log_slot(session_id, sub["code"], date_str, s["time"], s["spots"])
            if s["spots"] > 0:
                all_results.append((date_str, s["time"], s["spots"], s["interval_id"]))
        if args.verbose and slots:
            summary = ", ".join(f"{s['time']}({s['spots']})" for s in slots)
            print(f"  {date_str}: {summary}")

    db.close()
    elapsed = time.time() - t_start

    # Filter by target slot if specified
    if args.slot:
        matching = [r for r in all_results if args.slot in r[1]]
    else:
        matching = all_results

    if not matching:
        print(f"\nNo availability{f' for {args.slot}' if args.slot else ''} in next {args.days} days.")
        print(f"({elapsed:.1f}s)")
        return ExitCode.NO_AVAILABILITY

    # Display results
    print(f"\n{'='*50}")
    print(f"  AVAILABLE SLOTS")
    print(f"{'='*50}")
    for i, (date, slot_time, spots, _) in enumerate(matching):
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%a")
        spot_w = "spot" if spots == 1 else "spots"
        print(f"  [{i+1}] {date} ({day})  {slot_time}  — {spots} {spot_w}")
    print(f"{'='*50}")
    print(f"  ({elapsed:.1f}s, {len(dates)} dates checked)\n")

    # Interactive booking prompt
    choice = input("Book a slot? Enter number (or press Enter to skip): ").strip()
    if not choice:
        return ExitCode.SUCCESS

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(matching):
            date, slot_time, spots, interval_id = matching[idx]
            confirm = input(f"  Confirm booking {date} {slot_time}? (y/n): ").strip().lower()
            if confirm in ("y", "yes", "da"):
                print(f"  Booking...")
                if client.book_slot(interval_id):
                    print(f"  Booked! {date} {slot_time}")
                    return ExitCode.SUCCESS
                else:
                    print(f"  Booking failed.")
                    return ExitCode.BOOKING_FAILED
    except (ValueError, IndexError):
        print("  Invalid selection.")

    return ExitCode.SUCCESS


def _resolve_subscription(override=None):
    """Resolve subscription from CLI arg or env."""
    if override:
        return {"code": override, "name": "CLI"}
    subs = load_subscriptions()
    if subs:
        return subs[0]
    print("No subscription codes found. Set NEPTUN_SUBSCRIPTIONS or use -s CODE.")
    return None
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import cmd_check; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add cmd_check with interactive booking prompt"
```

---

### Task 8: `status` and `delete` commands

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add cmd_status and cmd_delete**

```python
def cmd_status(args):
    """Show current appointments."""
    creds = get_credentials()
    if not creds:
        print("Missing NEPTUN_EMAIL/NEPTUN_PASSWORD in .env")
        return ExitCode.UNKNOWN_ERROR

    client = BPSBClient(verbose=args.verbose)
    if not client.login(creds["email"], creds["password"]):
        print("Login failed.")
        return ExitCode.NETWORK_ERROR

    appointments = client.get_appointments()
    if not appointments:
        print("No appointments found.")
        return ExitCode.SUCCESS

    print(f"\n{'='*60}")
    print(f"  CURRENT APPOINTMENTS ({len(appointments)})")
    print(f"{'='*60}")
    for i, a in enumerate(appointments):
        print(f"  [{i+1}] {a['resource']}  {a['datetime']}  ({a['places']} places, {a['price']} RON)")
    print(f"{'='*60}\n")
    return ExitCode.SUCCESS


def cmd_delete(args):
    """Delete appointments interactively."""
    creds = get_credentials()
    if not creds:
        print("Missing NEPTUN_EMAIL/NEPTUN_PASSWORD in .env")
        return ExitCode.UNKNOWN_ERROR

    client = BPSBClient(verbose=args.verbose)
    if not client.login(creds["email"], creds["password"]):
        print("Login failed.")
        return ExitCode.NETWORK_ERROR

    appointments = client.get_appointments()
    if not appointments:
        print("No appointments found.")
        return ExitCode.SUCCESS

    # Display
    print(f"\n{'='*60}")
    print(f"  CURRENT APPOINTMENTS ({len(appointments)})")
    print(f"{'='*60}")
    for i, a in enumerate(appointments):
        print(f"  [{i+1}] {a['resource']}  {a['datetime']}  ({a['places']} places)")
    print(f"{'='*60}")

    choice = input("\nDelete which? Numbers (space-separated), 'all', or Enter to cancel: ").strip()
    if not choice:
        return ExitCode.SUCCESS

    if choice.lower() == "all":
        indices = list(range(len(appointments)))
    else:
        try:
            indices = [int(x) - 1 for x in choice.split()]
        except ValueError:
            print("Invalid input.")
            return ExitCode.UNKNOWN_ERROR

    to_delete = [appointments[i] for i in indices if 0 <= i < len(appointments) and appointments[i].get("delete_id")]

    if not to_delete:
        print("Nothing to delete.")
        return ExitCode.SUCCESS

    confirm = input(f"  Delete {len(to_delete)} appointment(s)? (y/n): ").strip().lower()
    if confirm not in ("y", "yes", "da"):
        print("  Cancelled.")
        return ExitCode.SUCCESS

    deleted = 0
    for a in to_delete:
        if client.delete_appointment(a["delete_id"]):
            print(f"  Deleted: {a['datetime']}")
            deleted += 1
        else:
            print(f"  Failed: {a['datetime']}")

    print(f"\n{deleted}/{len(to_delete)} deleted.")
    return ExitCode.SUCCESS
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import cmd_status, cmd_delete; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add cmd_status and cmd_delete with interactive flow"
```

---

### Task 9: `collect` command — silent data collection for cron

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add cmd_collect**

```python
def cmd_collect(args):
    """Collect availability data for all subscriptions (cron mode)."""
    subs = load_subscriptions()
    if args.subscription:
        subs = [{"code": args.subscription, "name": "CLI"}]
    if not subs:
        print("No subscription codes found.")
        return ExitCode.INVALID_SUBSCRIPTION

    db = DB(args.db)
    total_slots = 0
    errors = 0

    for sub in subs:
        client = BPSBClient(verbose=args.verbose)
        constraints = client.init_booking_session(sub["code"])
        if not constraints:
            print(f"Invalid subscription: {sub['code']}")
            errors += 1
            continue

        dates = candidate_dates(constraints, 30)
        session_id = str(uuid.uuid4())[:8]

        for date_str in dates:
            try:
                slots = client.get_slots_for_date(date_str)
                for s in slots:
                    db.log_slot(session_id, sub["code"], date_str, s["time"], s["spots"])
                    total_slots += 1
            except Exception as e:
                if args.verbose:
                    print(f"  Error {date_str}: {e}")
                errors += 1

        if args.verbose:
            print(f"  {sub['name']}: collected {total_slots} slots")

    db.close()
    print(f"Collected {total_slots} slots, {errors} errors.")
    return ExitCode.SUCCESS if errors == 0 else ExitCode.NETWORK_ERROR
```

**Step 2: Verify syntax**

Run: `uv run python -c "from neptun_fast import cmd_collect; print('OK')"`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add cmd_collect for silent cron data collection"
```

---

### Task 10: CLI entrypoint with argparse

**Files:**
- Modify: `neptun_fast.py`

**Step 1: Add main() with argument parser**

```python
def main():
    parser = argparse.ArgumentParser(description="Neptune — Fast sauna booking CLI")
    parser.add_argument("-s", "--subscription", help="Subscription code")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--db", default=DB_FILE, help="Database path")

    sub = parser.add_subparsers(dest="command")

    # check (default)
    p_check = sub.add_parser("check", help="Check availability and optionally book")
    p_check.add_argument("--slot", default=None, help='Filter by time slot (e.g. "17:30 - 21:00")')
    p_check.add_argument("--days", type=int, default=7, help="Days ahead to check (default: 7)")

    # status
    sub.add_parser("status", help="View current appointments")

    # delete
    sub.add_parser("delete", help="Delete appointments interactively")

    # collect
    sub.add_parser("collect", help="Collect availability data (for cron)")

    args = parser.parse_args()

    # Default to check if no command given
    if not args.command:
        args.command = "check"
        args.slot = None
        args.days = 7

    commands = {
        "check": cmd_check,
        "status": cmd_status,
        "delete": cmd_delete,
        "collect": cmd_collect,
    }

    try:
        exit_code = commands[args.command](args)
    except requests.RequestException as e:
        print(f"Network error: {e}")
        exit_code = ExitCode.NETWORK_ERROR
    except KeyboardInterrupt:
        print("\nCancelled.")
        exit_code = ExitCode.UNKNOWN_ERROR

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

**Step 2: Smoke test**

Run: `uv run python neptun_fast.py --help`
Run: `uv run python neptun_fast.py check --help`

**Step 3: Commit**

```bash
git add neptun_fast.py
git commit -m "feat: add CLI entrypoint with subcommands"
```

---

### Task 11: Update Makefile and wrapper script

**Files:**
- Modify: `Makefile`
- Modify: `check-availability.sh`

**Step 1: Update Makefile targets to use neptun_fast.py**

Replace the script references. Key targets:

```makefile
# Interactive check + book
check:
	uv run python neptun_fast.py check -v

# Check evening slot specifically
check-evening:
	uv run python neptun_fast.py check --slot "17:30 - 21:00" -v

# Appointment management
status:
	uv run python neptun_fast.py status

delete:
	uv run python neptun_fast.py delete

# Data collection
collect:
	uv run python neptun_fast.py collect

collect-verbose:
	uv run python neptun_fast.py collect -v
```

**Step 2: Simplify `check-availability.sh`**

```bash
#!/bin/bash
cd "$(dirname "$0")"
uv run python neptun_fast.py check --slot "17:30 - 21:00" -v
```

**Step 3: Verify**

Run: `make check-evening`

**Step 4: Commit**

```bash
git add Makefile check-availability.sh
git commit -m "feat: update Makefile and wrapper to use neptun_fast.py"
```

---

### Task 12: Live test all commands

**Step 1: Test check**

Run: `uv run python neptun_fast.py check --slot "17:30 - 21:00" -v`
Expected: Shows available evening slots, prompts to book (press Enter to skip).

**Step 2: Test status**

Run: `uv run python neptun_fast.py status -v`
Expected: Shows current appointments table.

**Step 3: Test collect**

Run: `uv run python neptun_fast.py collect -v`
Expected: Collects data for all subscriptions, prints summary.

**Step 4: Test default (no subcommand)**

Run: `uv run python neptun_fast.py`
Expected: Runs check with defaults.

**Step 5: Commit if all pass**

```bash
git add -A
git commit -m "feat: neptun_fast.py complete — HTTP-only sauna booking CLI"
```
