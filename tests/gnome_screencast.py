#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Record the screen (or an area) with GNOME Shell's built-in screencast until STOPFILE exists.

    python3 tests/gnome_screencast.py OUTPUT.mp4 STOPFILE [X Y WIDTH HEIGHT]

GNOME stops a screencast when the D-Bus connection that started it closes, so
this helper keeps the connection open while the recording runs. Needs GNOME Shell
and python3-gi. Used by tests/run_gui_test.sh --record.
"""

import os
import sys
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


def main(argv):
    if len(argv) not in (3, 7):
        sys.exit(__doc__)
    output, stopfile = os.path.abspath(argv[1]), argv[2]
    stem, ext = os.path.splitext(output)
    template = stem if ext.lower() in (".mp4", ".webm", ".mkv") else output  # GNOME adds the extension
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    proxy = Gio.DBusProxy.new_sync(bus, 0, None, "org.gnome.Shell.Screencast", "/org/gnome/Shell/Screencast",
                                   "org.gnome.Shell.Screencast", None)
    options = {"framerate": GLib.Variant("i", 15), "draw-cursor": GLib.Variant("b", False)}
    if len(argv) == 7:
        x, y, w, h = (int(v) for v in argv[3:7])
        ok, used = proxy.call_sync("ScreencastArea", GLib.Variant("(iiiisa{sv})", (x, y, w, h, template, options)),
                                   0, -1, None).unpack()
    else:
        ok, used = proxy.call_sync("Screencast", GLib.Variant("(sa{sv})", (template, options)), 0, -1, None).unpack()
    if not ok:
        sys.exit("GNOME Shell refused to start the screencast")
    print(f"recording to {used}", flush=True)
    try:
        while not os.path.exists(stopfile):
            time.sleep(0.2)
    finally:
        proxy.call_sync("StopScreencast", None, 0, -1, None)
    time.sleep(1)  # let GNOME finish writing the file
    if used != output and os.path.exists(used) and os.path.splitext(used)[1] == ext:
        os.replace(used, output)
        used = output
    print(f"recording stopped: {used}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
