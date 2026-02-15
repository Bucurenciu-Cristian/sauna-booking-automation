#!/bin/bash
cd "$(dirname "$0")"
uv run python neptun_fast.py check --slot "17:30 - 21:00" -v
