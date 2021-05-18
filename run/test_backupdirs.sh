#!/usr/bin/env bash
projectdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/../"

"$projectdir"run/backupdirs.py ~/TEST_backupdirs_all/ --files_single "$projectdir" -f d1 -f M5

