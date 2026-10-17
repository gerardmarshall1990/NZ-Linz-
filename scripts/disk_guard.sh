#!/bin/bash
# Disk guard for long jobs: if free space on / drops below MIN_GB (default 6), pause the given process trees (SIGSTOP) and print an alert; resume with `kill -CONT <pids>`.
# Usage: scripts/disk_guard.sh <pattern of the job's top process, e.g. "make bootstrap"> [min_gb]. Prints one line per event (use with a watcher).
pat="$1"; min="${2:-6}"
while true; do
  free=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
  if [ "$free" -lt "$min" ]; then
    pids=$(pgrep -f "$pat" | tr '\n' ' ')
    for p in $pids; do pkill -STOP -P "$p" 2>/dev/null; kill -STOP "$p" 2>/dev/null; done
    echo "DISK LOW: ${free} GB free (< ${min} GB). Paused: $pids. Resume with: kill -CONT $pids (and children)"; exit 2
  fi
  pgrep -f "$pat" >/dev/null || { echo "job finished; guard exiting (free ${free} GB)"; exit 0; }
  sleep 15
done
