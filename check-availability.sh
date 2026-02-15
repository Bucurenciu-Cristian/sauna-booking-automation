#!/bin/bash
# Check sauna availability for the 17:30-21:00 slot in the next 7 days
# Used by cron job to notify Kicky when evening slots are available

cd "$(dirname "$0")"

# Run status check to see current bookings
echo "=== Current Bookings ==="
uv run python neptun.py --status --headless 2>&1

# Run collect to check available slots (may fail, that's OK)
echo ""
echo "=== Collecting Availability Data ==="
uv run python neptun.py --collect --headless -v 2>&1

echo ""
echo "=== Trends ==="
uv run python neptun.py --trends --trends-days 7 2>&1 || echo "No trend data available"
