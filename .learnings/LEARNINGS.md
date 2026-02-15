# Learnings

## [LRN-20260216-001] best_practice

**Logged**: 2026-02-16T01:30:00Z
**Priority**: critical
**Status**: resolved
**Area**: backend

### Summary
BPSB booking uses a cart-based two-phase commit: /register adds to cart, /final commits the booking.

### Details
The `/client-interface/appointment-subscription/register` endpoint does NOT create a booking directly.
It adds the slot to a server-side cart (visible in the "Rezumatul comenzii tale" side panel).
The actual booking only happens when you hit `/client-interface/appointment-subscription/final`.
Without calling /final, spots are temporarily held but no appointment is created.
Cart items are scoped to the PHP session and expire when the session ends.
There is also a `/remove/{index}` endpoint to remove items from the cart before finalizing.

### Suggested Action
Always call /final after /register. Verify booking by checking the authenticated appointments page.

### Metadata
- Source: error (booking appeared to succeed but didn't create appointment)
- Related Files: neptun_fast.py, docs/api-discovery.md
- Tags: bpsb, booking, api

### Resolution
- **Resolved**: 2026-02-16T01:30:00Z
- **Commit**: fb56502
- **Notes**: Updated book_slot() to call /final after /register

---

## [LRN-20260216-002] correction

**Logged**: 2026-02-16T01:00:00Z
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
BPSB step4 HTML has interval ID BEFORE the time slot, not after. Regex must match in correct order.

### Details
The plan's regex assumed: `<h5>` → time → spots → `name="interval"` (time before interval).
Real HTML structure: `name="interval" value="ID"` → `<h5> Grupa HH:MM - HH:MM </h5>` → `Locuri disponibile: N`.
The fallback parser using independent findall() calls was silently mismatching times to interval IDs
(e.g., labeling interval 974 as "07:00" when it was actually "14:00").

### Suggested Action
When scraping HTML, always verify element order against real responses before writing regex.

### Metadata
- Source: error (booked wrong time slot)
- Related Files: neptun_fast.py
- Tags: regex, html-parsing, bpsb

### Resolution
- **Resolved**: 2026-02-16T01:00:00Z
- **Commit**: ac9efd5
- **Notes**: Rewrote regex to match interval → time → spots order

---

## [LRN-20260216-003] best_practice

**Logged**: 2026-02-16T00:45:00Z
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
argparse subcommands don't inherit parent parser arguments unless you use the parents= parameter.

### Details
Defining `-v` on the main parser and then calling `script.py check -v` fails because `-v` is not
registered on the `check` subparser. The fix is to create a shared `ArgumentParser(add_help=False)`
and pass it as `parents=[common]` to both the main parser and each subparser.

### Suggested Action
Always use the parents pattern when argparse subcommands need shared flags.

### Metadata
- Source: error (argparse unrecognized arguments)
- Related Files: neptun_fast.py
- Tags: argparse, python, cli

### Resolution
- **Resolved**: 2026-02-16T00:45:00Z
- **Commit**: 4bd2deb
- **Notes**: Used parents=[common] pattern for shared -v, -s, --db args

---
