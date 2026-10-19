#!/usr/bin/env bash
# Full test suite, protecting your saved inputs and the demo listings (the suite clears them). Exit code = the test result.
cd "$(dirname "$0")/.."
G=$(mktemp); python3 scripts/test_state_guard.py save "$G" || { echo "could not snapshot saved inputs: not running the tests"; exit 2; }
python3 -m pytest -q -p no:cacheprovider; rc=$?
python3 scripts/test_state_guard.py restore "$G"; rm -f "$G"; exit $rc
