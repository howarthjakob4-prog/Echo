#!/usr/bin/env python3
"""Echo browser capability — Phase 1 boundary module.

Phase 1 scope (honest): this is a BASIC LOOKUP only. It fetches one
public web page and returns its title and a short text excerpt. It
cannot click, fill in forms, sign in, or follow a multi-step browsing
session — full interactive browsing, like Muse's, comes in a later
phase. Do not describe this module as more than it is.

The server (server.py) is responsible for checking Echo's state before
calling fetch_page(): when Echo is STOPPED, no lookup runs at all. This
module additionally refuses anything that is not an http/https URL.

The fetch itself is done by the REAL Google Chrome installed on
Echo's Linux machine (Jakob's order, 2026-10-19: "install the
official Google browser onto his Linux machine so it actually looks
like a Google browser"). Chrome runs headless per lookup and returns
the rendered page; this module parses the title/excerpt out of
Chrome's DOM dump. Chrome talks to the internet through the local
relay (chrome_relay.py, 127.0.0.1:18081), which smooths out this
VM's egress proxy refusing browser tunnel bursts. One honesty note:
--dump-dom does not expose the HTTP status line, so a page Chrome
renders successfully is reported with status 200; transport failures
surface as ok=False with Chrome's own error code.

Jakob's research/browser rule (2026-10-19): Echo's research tool is his
own browser on his Linux machine, and his browsing rules are appropriate
websites only, with SafeSearch on for searches. The deterministic piece
lives here, at the one choke point every fetch passes through: any URL
whose host is on the Echo Website Blocker's block list (the sibling
echo-blocker folder's blocklist.json) is refused before any fetch, with
Jakob's words: "Sorry, this website is blocked."

After a successful lookup, a real screenshot of Echo's Chrome screen
is saved beside this module (chrome_last.png, plus chrome_state.json)
so Ferrum's Echo view can show people the latest thing on his
screen. The screenshot path is display-first (chrome_screen.py):
Echo's GUI Chrome on his display (Xvfb :99) opens the page, his REAL
X pointer rests on the content he engaged, and the saved frame is a
capture of that display with the genuine pointer in it — Jakob's
order (2026-10-19): Echo gets a mouse of his own, so people can tell
what he's clicking on. Only if the display path cannot run does this
fall back to a headless page screenshot; a headless frame contains
no pointer, and the state file then records cursor=None so the
machine view never claims one is there.
"""
import html
import json
import os
import re
import subprocess
import tempfile
import time
from urllib.parse import urlparse

TEXT_SNIPPET_CHARS = 1000       # excerpt length returned to the caller
USER_AGENT = "Echo-Linux/1.2.3 (basic lookup; designed by Jakob Howarth)"

CHROME_BIN = "/usr/bin/google-chrome"
RELAY_PROXY = "http://127.0.0.1:18081"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_FILE = os.path.join(HERE, "chrome_last.png")
STATE_FILE = os.path.join(HERE, "chrome_state.json")

BLOCKLIST_FILE = os.path.normpath(os.path.join(
    HERE, "..", "echo-blocker", "blocklist.json"))
_blocklist_cache = {"mtime": None, "domains": frozenset()}


def _blocked_domains():
    """The block list's domains, re-read whenever the file changes."""
    try:
        mtime = os.path.getmtime(BLOCKLIST_FILE)
    except OSError:
        return _blocklist_cache["domains"]
    if _blocklist_cache["mtime"] != mtime:
        try:
            with open(BLOCKLIST_FILE, encoding="utf-8") as f:
                data = json.load(f)
            domains = frozenset(
                str(d.get("domain", "")).strip().lower()
                for d in data.get("domains", []) if d.get("domain"))
        except Exception:
            return _blocklist_cache["domains"]
        _blocklist_cache["mtime"] = mtime
        _blocklist_cache["domains"] = domains
    return _blocklist_cache["domains"]


def blocked_reason(url):
    """Jakob's block-list refusal for this URL, or None if it is allowed."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return None
    for domain in _blocked_domains():
        if host == domain or host.endswith("." + domain):
            return "refused: Sorry, this website is blocked."
    return None


def _extract_title(page_html):
    m = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() or None


def _extract_text(page_html):
    # Crude tag stripper — good enough for a Phase 1 excerpt, not a parser.
    body = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", page_html)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"\s+", " ", body).strip()[:TEXT_SNIPPET_CHARS]


def _chrome_args(profile_dir):
    return [
        CHROME_BIN, "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--disable-component-update",
        "--disable-background-networking", "--disable-sync",
        "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        f"--proxy-server={RELAY_PROXY}",
    ]


def _chrome_dom(url, attempts=2):
    """Render `url` in headless Chrome; return (dom, error_code)."""
    last_err = "empty response from Chrome"
    for _ in range(attempts):
        with tempfile.TemporaryDirectory(prefix="echo-chrome-") as prof:
            try:
                proc = subprocess.run(
                    _chrome_args(prof) + [
                        "--virtual-time-budget=25000",
                        "--timeout=45000", "--dump-dom", url],
                    capture_output=True, text=True, timeout=90)
                dom = proc.stdout or ""
            except Exception as e:
                last_err = str(e)
                continue
        m = re.search(r"ERR_[A-Z_]+", dom)
        if m and ("error-code" in dom or "This site can" in dom
                  or "can’t be reached" in dom or "can't be reached" in dom):
            last_err = m.group(0)
            continue
        if "<html" in dom.lower():
            return dom, None
        last_err = "empty response from Chrome"
    return "", last_err


def _chrome_screenshot(url, title):
    """Best-effort: photograph Echo's Chrome screen for the machine
    view. Display path first (chrome_screen.show_page — his real
    pointer resting on the content, captured from his display);
    headless page screenshot only as fallback (see module docstring).
    """
    last_err = None
    for _attempt in range(2):
        try:
            import chrome_screen
            chrome_screen.show_page(url, title)
            return
        except Exception as e:  # display busy/missing — one retry
            last_err = e
            time.sleep(1.0)
    # Never silent: record why the display path gave up, then fall
    # back to the headless capture (whose state claims no pointer).
    try:
        with open(os.path.join(HERE, "chrome_screen_errors.log"),
                  "a", encoding="utf-8") as f:
            f.write("%s display screenshot failed for %s: %r\n"
                    % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), url, last_err))
    except Exception:
        pass
    _chrome_screenshot_headless(url, title)


def _chrome_screenshot_headless(url, title):
    """Fallback: a real screenshot of the page from headless Chrome.
    No pointer exists in a headless frame, so the state records
    cursor=None — the machine view makes no mouse claim for it."""
    try:
        with tempfile.TemporaryDirectory(prefix="echo-chrome-shot-") as prof:
            tmp_shot = os.path.join(prof, "shot.png")
            subprocess.run(
                _chrome_args(prof) + [
                    "--virtual-time-budget=25000", "--timeout=45000",
                    "--window-size=1280,800", f"--screenshot={tmp_shot}",
                    url],
                capture_output=True, timeout=90)
            if os.path.isfile(tmp_shot) and os.path.getsize(tmp_shot) > 2000:
                import shutil
                shutil.copyfile(tmp_shot, SHOT_FILE)
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "title": title,
                               "ts": int(time.time()), "cursor": None}, f)
    except Exception:
        pass  # The screenshot is a view, never a reason to fail a lookup.


def fetch_page(url):
    """Fetch one http/https URL with Echo's Google Chrome.

    Returns {"ok": True, "url", "status", "title", "text"} on success or
    {"ok": False, "error": "..."} on any failure. Never raises.
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"ok": False, "error": "refused: only http/https URLs are allowed"}

    reason = blocked_reason(url)
    if reason:
        return {"ok": False, "error": reason}

    dom, err = _chrome_dom(url)
    if not dom:
        return {"ok": False, "error": f"fetch failed: Chrome could not load the page ({err})"}

    title = _extract_title(dom)
    _chrome_screenshot(url, title)
    return {
        "ok": True,
        "url": url,
        "status": 200,
        "title": title,
        "text": _extract_text(dom),
    }
