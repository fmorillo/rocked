#!/usr/bin/env bash

process_add.py

#trap "kill ${sid[@]}" INT
"$@"

process_remove.py
