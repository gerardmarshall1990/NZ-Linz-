#!/bin/bash
# Start the local (apt) PostgreSQL 16 cluster if it is not running. Sandbox-only helper; docker compose is the normal route.
pg_lsclusters | grep -q online || { pg_ctlcluster 16 main start 2>&1; sleep 3; }
pg_lsclusters | tail -1
