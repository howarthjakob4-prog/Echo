#!/usr/bin/env python3
"""Echo's Chrome screen — the display path, and Echo's mouse.

Jakob's orders (2026-10-19): Echo's browser is the REAL Google
Chrome installed on his Linux machine, and Echo needs a mouse of his
own "so the people can tell what he's clicking on. Like you do."

Echo's Chrome lives on a virtual display (Xvfb :99). This module is
how Echo presents a page on that display and how his screenshots are
taken:

- His GUI Chrome is navigated to the page (omnibox, via xdotool —
  the URL is pasted through the X clipboard because xdotool typing
  mangles characters like ':' often enough to matter).
- His REAL X pointer is moved (xdotool mousemove) onto the content
  he engaged: the center of the page's main heading / main text /
  main link, measured from the page's own layout by
  chrome_geometry.mjs at the same viewport size his display window
  shows. If a page has none of those, the pointer rests mid-page.
- The screenshot is a capture of the actual display (ffmpeg
  x11grab, -draw_mouse 1). The pointer in the picture is the X
  server's own cursor image at its true position — the same way the
  verified echo-real-chrome.png was captured. NOTHING here draws or
  composites a cursor; if this display path cannot run, callers fall
  back to a plain headless page screenshot and the state file says
  cursor=None — no pointer is ever faked.

State is shared with the machine view through chrome_state.json
(url, title, ts, shown_url, cursor{x, y, on, note}) — Ferrum serves
it in its "Echo's Chrome" panel.

CLI:  python3 chrome_screen.py --show <url> [--title T]
      python3 chrome_screen.py --refresh
Both print a JSON state line; exit code is non-zero on failure.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_FILE = os.path.join(HERE, "chrome_last.png")
STATE_FILE = os.path.join(HERE, "chrome_state.json")
GEOMETRY_JS = os.path.join(HERE, "chrome_geometry.mjs")

DISPLAY = ":99"
SCREEN_W, SCREEN_H = 1280, 800
# Echo's Chrome window fills the display; its page content begins
# this far below the top of the window (tab strip + toolbar),
# measured against his real google.com screen.
UI_OFFSET = 88
VIEWPORT_W = 1280
VIEWPORT_H = SCREEN_H - UI_OFFSET  # 711: content height GEOMETRY uses


def _env():
    env = dict(os.environ)
    env["DISPLAY"] = DISPLAY
    return env


def _run(cmd, timeout=30, inp=None):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True,
                          timeout=timeout, env=_env())


def _chrome_window():
    """The (window_id, title) of Echo's real Chrome window on :99."""
    try:
        out = _run(["xdotool", "search", "--class", "chrome"], timeout=15)
        ids = [w.strip() for w in out.stdout.splitlines() if w.strip()]
    except Exception:
        return None, None
    for wid in ids:
        try:
            geo = _run(["xdotool", "getwindowgeometry", wid],
                       timeout=10).stdout
            name = _run(["xdotool", "getwindowname", wid],
                        timeout=10).stdout.strip()
        except Exception:
            continue
        # "Geometry: 1279x799" — the browser window fills the display;
        # the other chrome-class windows are tiny stubs.
        if "Geometry:" in geo:
            dims = geo.split("Geometry:")[1].strip().split()[0]
            try:
                w = int(dims.split("x")[0])
            except ValueError:
                continue
            if w > 1000:
                return wid, name
    return None, None


def _window_title(wid):
    try:
        return _run(["xdotool", "getwindowname", wid],
                    timeout=10).stdout.strip()
    except Exception:
        return ""


def _set_clipboard(text):
    # xclip forks to hold the selection; -loops 1 makes it exit after
    # the paste has been served once. stdio goes to DEVNULL so the
    # detached holder cannot keep a caller's pipe open.
    with open(os.devnull, "wb") as devnull:
        subprocess.Popen(
            ["xclip", "-loops", "1", "-selection", "clipboard"],
            stdin=subprocess.PIPE, stdout=devnull, stderr=devnull,
            env=_env()).communicate(text.encode(), timeout=15)


def _navigate(wid, url, expect_title=None):
    """Open `url` in Echo's GUI Chrome via its omnibox; return title."""
    _run(["xdotool", "mousemove", "500", "65", "click", "1"], timeout=15)
    time.sleep(0.3)
    _run(["xdotool", "key", "ctrl+a"], timeout=10)
    _set_clipboard(url)
    _run(["xdotool", "key", "ctrl+v"], timeout=10)
    _run(["xdotool", "key", "Return"], timeout=10)
    prev, stable = "", 0
    deadline = time.time() + 45
    while time.time() < deadline:
        time.sleep(1.2)
        title = _window_title(wid)
        if expect_title and expect_title in title:
            return title
        if title and title == prev and title != "google-chrome":
            stable += 1
            if stable >= 2:
                return title
        else:
            stable = 0
        prev = title
    return _window_title(wid)


def _heading_point(url):
    """Where the page's main content renders, from Chrome's own layout."""
    try:
        out = subprocess.run(
            ["node", GEOMETRY_JS, url, str(VIEWPORT_W), str(VIEWPORT_H)],
            capture_output=True, text=True, timeout=120)
        lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
        if lines:
            data = json.loads(lines[-1])
            if data.get("found"):
                return data
    except Exception:
        pass
    return None


def _capture_display(dest):
    """Photograph Echo's display, real pointer included (x11grab).

    The temp frame name is unique per process and the grab is
    retried once: this runs inside Echo's server while Ferrum may
    ask for a refresh at the same moment, and two captures must
    never trip over each other's temp file."""
    for _attempt in range(2):
        tmp = "%s.tmp.%d.png" % (dest, os.getpid())
        try:
            _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab",
                  "-draw_mouse", "1",
                  "-video_size", f"{SCREEN_W}x{SCREEN_H}",
                  "-i", DISPLAY, "-frames:v", "1", tmp], timeout=60)
            if os.path.isfile(tmp) and os.path.getsize(tmp) > 5000:
                os.replace(tmp, dest)
                return True
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        time.sleep(0.6)
    return False


def _move_pointer(x, y):
    """Move Echo's real X pointer to (x, y) and confirm it arrived.

    Deliberately NOT `xdotool mousemove --sync`: under a busy X
    server (Chrome mid-render on this one-display machine) the
    --sync wait can hang indefinitely. A plain warp lands at once;
    we then poll the pointer's actual location briefly and re-warp
    once if it is not there yet."""
    for _attempt in range(2):
        _run(["xdotool", "mousemove", str(x), str(y)], timeout=10)
        for _poll in range(6):
            time.sleep(0.15)
            try:
                out = _run(["xdotool", "getmouselocation"],
                           timeout=5).stdout
            except Exception:
                continue
            # "x:633 y:285 screen:0 window:..."
            parts = dict(tok.split(":", 1) for tok in out.split()
                         if ":" in tok)
            try:
                if abs(int(parts["x"]) - x) <= 2 and \
                        abs(int(parts["y"]) - y) <= 2:
                    return True
            except (KeyError, ValueError):
                continue
    return False


def _read_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _clean_title(window_title, fallback=None):
    t = (window_title or "").strip()
    suffix = " - Google Chrome"
    if t.endswith(suffix):
        t = t[: -len(suffix)]
    return t or fallback


def show_page(url, title=None):
    """Put `url` on Echo's Chrome screen, rest his mouse on its main
    content, photograph the display, and record the state.

    Returns the state dict. Raises on failure (callers fall back)."""
    wid, _ = _chrome_window()
    if not wid:
        raise RuntimeError("Echo's GUI Chrome is not running on :99")
    state = _read_state()

    point = _heading_point(url)

    if state.get("shown_url") != url:
        win_title = _navigate(wid, url, expect_title=title)
        shown_title = title or _clean_title(win_title)
    else:
        shown_title = title or state.get("title")

    if point:
        dx = max(0, min(SCREEN_W - 1, int(point["cx"])))
        dy = max(0, min(SCREEN_H - 1, UI_OFFSET + int(point["cy"])))
        on_text = (point.get("text") or "").strip() or None
        kind = point.get("kind")
    else:
        dx, dy, on_text, kind = SCREEN_W // 2, UI_OFFSET + 300, None, None

    if kind == "heading" and on_text:
        note = ("Echo's mouse is resting on the heading \u201c%s\u201d "
                "of the page he just read" % on_text)
    elif kind == "text":
        note = "Echo's mouse is resting on the main text of the page he just read"
    elif kind == "link" and on_text:
        note = ("Echo's mouse is resting on a link (\u201c%s\u201d) "
                "on the page he just read" % on_text)
    else:
        note = "Echo's mouse is on the page he just read"

    _move_pointer(dx, dy)
    time.sleep(0.35)
    if not _capture_display(SHOT_FILE):
        raise RuntimeError("display capture failed")

    state = {"url": url, "title": shown_title, "ts": int(time.time()),
             "shown_url": url,
             "cursor": {"x": dx, "y": dy, "on": on_text, "note": note}}
    _write_state(state)
    return state


def refresh():
    """Re-photograph Echo's display as it stands — his pointer put
    back at the last place he acted, if we know it."""
    wid, _ = _chrome_window()
    if not wid:
        raise RuntimeError("Echo's GUI Chrome is not running on :99")
    state = _read_state()
    cursor = state.get("cursor") or {}
    if cursor.get("x") is not None and cursor.get("y") is not None:
        _move_pointer(int(cursor["x"]), int(cursor["y"]))
        time.sleep(0.3)
    if not _capture_display(SHOT_FILE):
        raise RuntimeError("display capture failed")
    state["ts"] = int(time.time())
    if not state.get("url"):
        state["url"] = "https://www.google.com"
        state["title"] = _clean_title(_window_title(wid))
    _write_state(state)
    return state


def main(argv):
    try:
        if "--refresh" in argv:
            result = refresh()
        elif "--show" in argv:
            i = argv.index("--show")
            url = argv[i + 1]
            title = None
            if "--title" in argv:
                title = argv[argv.index("--title") + 1]
            result = show_page(url, title)
        else:
            print(json.dumps({"ok": False,
                              "error": "usage: --show <url> | --refresh"}))
            return 2
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
