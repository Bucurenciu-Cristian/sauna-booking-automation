.PHONY: help install check check-evening status delete collect collect-verbose db-status db-availability db-cleanup db-clean install-cron clean

help:
	@echo "Neptune Sauna Booking CLI (HTTP-only)"
	@echo "======================================"
	@echo ""
	@echo "Interactive Booking:"
	@echo "  make check          - Check availability and optionally book"
	@echo "  make check-evening  - Check evening slot (17:30 - 21:00)"
	@echo ""
	@echo "Appointment Management:"
	@echo "  make status         - View current appointments"
	@echo "  make delete         - Delete appointments interactively"
	@echo ""
	@echo "Data Collection (for cron):"
	@echo "  make collect        - Collect availability for all subscriptions"
	@echo "  make collect-verbose - Collect with verbose output"
	@echo ""
	@echo "Database:"
	@echo "  make db-status      - Show database statistics"
	@echo "  make db-availability - Show recent availability data"
	@echo "  make db-cleanup     - Remove invalid records from database"
	@echo "  make db-clean       - Remove database (careful!)"
	@echo ""
	@echo "Setup:"
	@echo "  make install        - Install dependencies with uv"
	@echo "  make install-cron   - Install cron job for daily collection"
	@echo "  make clean          - Clean caches and temp files"

install:
	uv sync
	@echo "Dependencies installed with uv"

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

# Database management
db-status:
	@echo "Database Statistics:"
	@echo "===================="
	@sqlite3 neptun.db "SELECT 'Availability records: ' || COUNT(*) FROM availability;" 2>/dev/null || echo "No database found"

db-availability:
	@echo "Recent Availability Data:"
	@echo "========================="
	@sqlite3 -header -column neptun.db \
		"SELECT date, time_slot, spots_available, subscription_code, timestamp \
		FROM availability \
		WHERE date >= date('now') AND time_slot LIKE '%:%' \
		ORDER BY date, time_slot \
		LIMIT 20;" 2>/dev/null || echo "No data found"

db-cleanup:
	@echo "Cleaning invalid time_slot records..."
	@sqlite3 neptun.db "DELETE FROM availability WHERE time_slot NOT LIKE '%:%';" 2>/dev/null || true
	@echo "Cleaned. Remaining valid records:"
	@sqlite3 neptun.db "SELECT COUNT(*) FROM availability WHERE time_slot LIKE '%:%';" 2>/dev/null || echo "0"

db-clean:
	rm -f neptun.db
	@echo "Database removed"

# Cron installation
install-cron:
	@echo "Installing cron job for Neptune..."
	@mkdir -p ~/logs
	crontab cron/neptun.crontab
	@echo "Crontab installed. View with: crontab -l"
	@echo "Logs will be written to: ~/logs/neptun-collect.log"

# Cleanup
clean:
	rm -rf __pycache__/
	@echo "Temp files cleaned"
