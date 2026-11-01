#!/bin/sh
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Run the FreeCAD GUI test (tests/freecad_gui_test.py) and print its report.
#
#   tests/run_gui_test.sh [--flatpak | --native] [--record VIDEO.mp4 [--area X,Y,W,H]]
#                         [--pause SECONDS] [-- FREECAD-ARGS...]
#
#   --flatpak / --native  use the FreeCAD Flatpak (org.freecad.FreeCAD) or `freecad` from PATH
#                         (default: native if found, else the Flatpak)
#   --record FILE         record the screen with GNOME's built-in screencast (needs GNOME Shell,
#                         python3-gi); implies --pause 1.5 so the steps can be followed
#   --area X,Y,W,H        record only this screen area (e.g. 0,32,1920,1048 below the top bar)
#                         The recording shows whatever is in that area: keep other windows away,
#                         tick "Don't show this start page again" on FreeCAD's Start page (it lists
#                         your recent files) and review the video before publishing it.
#   --pause SECONDS       wait after each step (demo mode)
#
# Needs the workbench in FreeCAD's Mod folder and a solver the preferences find
# (Edit > Preferences > OpenRadioss). Report and screenshots go to $ORFE_OUT
# (default ~/orfe_gui_test_<date>). Exit code 0 when every check passed.

set -u
here=$(cd "$(dirname "$0")" && pwd)
mode="" record="" area="" pause=""
while [ $# -gt 0 ]; do
    case "$1" in
        --flatpak) mode=flatpak ;;
        --native) mode=native ;;
        --record) record=$(realpath -m "$2"); shift ;;
        --area) area=$(echo "$2" | tr ',' ' '); shift ;;
        --pause) pause="$2"; shift ;;
        --) shift; break ;;
        -h|--help) sed -n '3,22p' "$0"; exit 0 ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
    shift
done
[ -n "$record" ] && [ -z "$pause" ] && pause=1.5
out=${ORFE_OUT:-$HOME/orfe_gui_test_$(date +%Y%m%d_%H%M%S)}
mkdir -p "$out"

if [ -z "$mode" ]; then
    if command -v freecad >/dev/null 2>&1; then mode=native; else mode=flatpak; fi
fi

run_freecad() {
    if [ "$mode" = flatpak ]; then
        flatpak run --env=ORFE_OUT="$out" --env=ORFE_DEMO_PAUSE="${pause:-0}" \
            --env=ORFE_SYNC_RECORDER="$sync" org.freecad.FreeCAD "$@" "$here/freecad_gui_test.py"
    else
        ORFE_OUT="$out" ORFE_DEMO_PAUSE="${pause:-0}" ORFE_SYNC_RECORDER="$sync" \
            freecad "$@" "$here/freecad_gui_test.py"
    fi
}

wait_for() {  # wait_for FILE SECONDS PID: until FILE exists, the timeout passes or PID ends
    i=0
    while [ ! -e "$1" ] && [ $i -lt $(($2 * 5)) ] && kill -0 "$3" 2>/dev/null; do sleep 0.2; i=$((i + 1)); done
    [ -e "$1" ]
}

rm -f "$out/.ready" "$out/.recording" "$out/.finished" "$out/.recording_stopped" "$out/.stop_recording"
if [ -z "$record" ]; then
    sync=0
    run_freecad "$@"
    status=$?
else
    # Record only while the test runs: it signals .ready (window set up, Start page closed) and
    # .finished (before closing), so the video shows neither the desktop nor recent files.
    sync=1
    run_freecad "$@" &
    freecad_pid=$!
    if wait_for "$out/.ready" 180 "$freecad_pid"; then
        # shellcheck disable=SC2086
        python3 "$here/gnome_screencast.py" "$record" "$out/.stop_recording" $area &
        recorder=$!
        sleep 1
        touch "$out/.recording"
        wait_for "$out/.finished" 1800 "$freecad_pid"
        touch "$out/.stop_recording"
        wait "$recorder"
        touch "$out/.recording_stopped"
    else
        echo "the test did not start (no $out/.ready); not recording" >&2
    fi
    wait "$freecad_pid"
    status=$?
    rm -f "$out/.ready" "$out/.recording" "$out/.finished" "$out/.recording_stopped" "$out/.stop_recording"
fi

cat "$out/report.txt" 2>/dev/null || echo "no report written to $out/report.txt" >&2
exit $status
