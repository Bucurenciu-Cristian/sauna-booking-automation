# CLAUDE.md

## Project Overview

Neptune is a fast HTTP-only CLI for booking sauna reservations on the BPSB system (Baia Populara Sibiu). No browser needed — uses direct HTTP requests via `requests.Session()`.

**Active script:** `neptun_fast.py` (~300 lines)
**Legacy script:** `neptun.py` (~2500 lines, Selenium-based, superseded)

## File Structure

```
├── neptun_fast.py       # Active CLI script (HTTP-only)
├── neptun.py            # Legacy Selenium script (not used)
├── neptun.db            # SQLite database (auto-created)
├── .env                 # Credentials and config (not committed)
├── Makefile             # Build and run commands
├── check-availability.sh # Wrapper for evening slot check
├── pyproject.toml       # uv project config
├── docs/
│   ├── api-discovery.md # All BPSB endpoints and payloads
│   └── plans/           # Implementation plans
└── .learnings/          # Session learnings and error logs
```

## Dependencies and Setup

**Requirements:** Python 3.13, uv

```bash
uv sync                  # Install dependencies
```

**Environment variables (`.env`):**
```bash
NEPTUN_SUBSCRIPTIONS='5642ece785:Kicky,3adc06c0e8:Adrian'
NEPTUN_EMAIL=your@email.com
NEPTUN_PASSWORD=yourpassword
```

## Running

```bash
make check               # Check availability + interactive booking
make check-evening       # Check 17:30-21:00 slot specifically
make status              # View current appointments (requires login)
make delete              # Delete appointments interactively
make collect             # Collect availability data (for cron)
make collect-verbose     # Collect with verbose output
```

Direct CLI usage:
```bash
uv run python neptun_fast.py check -v --days 14 --slot "17:30 - 21:00"
uv run python neptun_fast.py check -s 5642ece785 --days 7
uv run python neptun_fast.py status -v
uv run python neptun_fast.py delete
uv run python neptun_fast.py collect -v
```

## Architecture

### BPSBClient class

Wraps all HTTP interactions with the BPSB booking system.

**Key methods:**
- `init_booking_session(code)` — walks steps 1-3, returns date constraints + subscription info
- `get_slots_for_date(date)` — queries step4 for available slots on a date
- `book_slot(interval_id)` — two-phase: add to cart (`/register`) then commit (`/final`)
- `login(email, password)` — authenticates with CSRF token
- `get_appointments()` — lists booked appointments (must be logged in)
- `delete_appointment(id)` — deletes appointment by base64 ID

**Subscription info** (parsed from step2):
- `sub_info["sessions_remaining"]` — sessions left on subscription
- `sub_info["valid_to"]` — subscription expiry date
- `sub_info["type"]` — subscription type name

### BPSB Booking Flow (HTTP)

```
Step 1: GET  /step1              → establish PHP session (PHPSESSID cookie)
Step 2: POST /step2              → submit subscription code, get sub_id + resource_id + metadata
Step 3: POST /step3              → select resource, get datepicker constraints
Step 4: POST /step4              → get slots for a date (repeatable within session)
Step 5: POST /register           → add slot to cart (temporary hold)
Step 6: GET  /final              → commit cart → real appointment created
        GET  /remove/{index}     → remove item from cart (0-based)
```

**Critical:** `/register` only adds to cart. Without `/final`, nothing is booked.
The confirmation text is: "Programarea a fost adaugata cu succes"

**Slot HTML structure** (step4): interval ID comes BEFORE time in the DOM:
```html
<input name="interval" value="972">
<h5>Grupa 07:00 - 10:30</h5>
<p>Locuri disponibile: 18</p>
```

### DB class

Minimal SQLite logger. Single table:
```sql
availability(id, timestamp, subscription_code, date, time_slot, spots_available, session_id)
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid subscription |
| 2 | No availability |
| 3 | Booking failed |
| 4 | Network error |
| 99 | Unknown error |

## Configuration

**Subscription format** in `.env`:
```
NEPTUN_SUBSCRIPTIONS='code1:Name1,code2:Name2'
```

**Login credentials** (needed for `status` and `delete` commands):
```
NEPTUN_EMAIL=your@email.com
NEPTUN_PASSWORD=yourpassword
```

## Date Constraints

The datepicker has constraints parsed from step3 JS:
- `daysOfWeekDisabled: "0,1"` — Sunday (0) and Monday (1) closed
- Holiday blackout dates hardcoded in JS
- `valabilityEnd` — subscription expiry (max 30 days ahead)

## Performance

| Operation | Selenium | HTTP |
|-----------|----------|------|
| Check 7 dates | ~30-60s | **2s** |
| Check 30 dates | ~2-3 min | **10s** |
| Login + list | ~8-10s | **1.5s** |
| Memory | ~200MB | ~5MB |

## Cron Setup

```bash
# Every 2 hours, collect availability data
0 */2 * * * cd /path/to/project && make collect >> ~/logs/neptun.log 2>&1
```

Non-interactive mode is safe — `input()` prompts are skipped when stdin is not a TTY.

## API Reference

See `docs/api-discovery.md` for full endpoint documentation with payloads and responses.

# currentDate
Today's date is 2026-02-16.

      IMPORTANT: this context may or may not be relevant to your tasks. You should not respond to this context unless it is highly relevant to your task.
