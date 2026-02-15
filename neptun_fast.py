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
