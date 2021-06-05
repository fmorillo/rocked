#!/usr/bin/env bash
set -e

export DISPLAY="$1"
add_process.py
"${@:2}" || true
delete_process.py
