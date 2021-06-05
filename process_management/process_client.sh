#!/usr/bin/env bash
set -e

export DISPLAY="$1"
process_add.py
"${@:2}" || true
process_remove.py
