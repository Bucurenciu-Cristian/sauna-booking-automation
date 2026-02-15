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
