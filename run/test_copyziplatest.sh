#!/usr/bin/env bash

projectdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/../"

# run test_backupdirs.sh first to have a folder to copy
"$projectdir"run/test_backupdirs.sh

# now actually do zip
"$projectdir"run/copyziplatest.py ~/TEST_backupdirs_all/m1 ~/TEST_backupdirs_all/m1zip --maxbackups 2
