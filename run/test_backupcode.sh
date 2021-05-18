#!/usr/bin/env bash
projectdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/../"

allcode=$("$projectdir"submodules/allcode-list/getallcode_func.py --files_single "$projectdir")

"$projectdir"run/backupcode.py ~/TEST_backupcode_all/ --files_aslines "$allcode" -f d1 -f M5
