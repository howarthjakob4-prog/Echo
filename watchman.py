"""Watchman mode for Echo (built 2026-10-26, Jakob's hackathon pick).

Echo watches the house himself: a background thread polls the Ferrum
house-status feed every POLL_INTERVAL_SECONDS, keeps the last-seen
per-service state, and when a service flips up->down or down->up it

  * appends a report entry to watchman_reports.jsonl (append-only,
    the same pattern as the activity log and the tickets file), and
  * queues a proactive one-line report, in Echo's own factual style,
    which server.py prepends — once — to his next /chat reply.

House-status questions in chat ("how's the house", "what's down") are
answered from this data BY ASSEMBLY. No LLM ever touches these lines:
the numbers must be exact.

Sources: the primary source is the public status feed (a plain GET —
read-only, like all of Echo's network use). When the fetch fails, the
watchdog's local reported_state.json serves as the fallback. Every
check records which source served it.

STOP wins over everything, as everywhere in Echo: while Echo is
stopped the watcher does not poll and files no reports, and /watchman
reports watching: false with reason "stopped".

Test hooks (environment only; production uses the defaults):
  ECHO_WATCHMAN_FEED_URL      — feed URL, or a local file path (fixture)
  ECHO_WATCHMAN_FALLBACK_FILE — fallback state file path
  ECHO_WATCHMAN_REPORTS_FILE  — reports JSONL path
  ECHO_WATCHMAN_INTERVAL      — poll interval in seconds
"""

import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _LOCAL_TZ = ZoneInfo("America/New_York")
except Exception:  # no tzdata — fall back to the machine's local time
    _LOCAL_TZ = None

HERE = os.path.dirname(os.path.abspath(__file__))

POLL_INTERVAL_SECONDS = 20
FEED_URL = os.environ.get(
    "ECHO_WATCHMAN_FEED_URL",
    "https://howarthjakob4-prog.github.io/ferrum-ai-status/status.json")
FALLBACK_FILE = os.environ.get(
    "ECHO_WATCHMAN_FALLBACK_FILE",
    os.path.expanduser("~/workspace/server-watchdog/reported_state.json"))
REPORTS_FILE = os.environ.get(
    "ECHO_WATCHMAN_REPORTS_FILE",
    os.path.join(HERE, "watchman_reports.jsonl"))
try:
    _POLL = int(os.environ.get("ECHO_WATCHMAN_INTERVAL",
                               POLL_INTERVAL_SECONDS))
except ValueError:
    _POLL = POLL_INTERVAL_SECONDS

_lock = threading.Lock()
_started = False
_is_stopped_fn = None
_log_fn = None

# The watcher's memory. _state is None until the first successful
# check sets the baseline — the first check never files reports,
# because there is nothing to compare against yet.
_state = None            # {service_key: bool}
_source = None           # "feed" | "local-fallback" | None
_last_check = None       # ISO timestamp (UTC) of the last good check
_pending = []            # queued proactive report lines, undelivered
_recent = []             # last report entries (dicts), newest last

HOUSE_QUESTION_PATTERNS = (
    "how's the house",
    "hows the house",
    "how is the house",
    "house status",
    "house report",
    "what's down",
    "whats down",
    "what is down",
    "anything down",
    "how are the services",
    "watchman",
)


def _now_local_hhmm():
    now = datetime.now(_LOCAL_TZ) if _LOCAL_TZ else datetime.now()
    return now.strftime("%H:%M")


def _fetch_feed():
    """Return the parsed feed dict, reading FEED_URL as a URL or, when
    it is a plain path, as a local file (the fixture route for tests)."""
    if FEED_URL.startswith(("http://", "https://")):
        req = urllib.request.Request(
            FEED_URL, headers={"User-Agent": "Echo-Watchman/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read().decode("utf-8"))
    with open(FEED_URL, encoding="utf-8") as f:
        return json.load(f)


def _read_source():
    """One check's data: (state_map, source_label). The public feed is
    primary; the watchdog's local reported_state.json is the fallback
    when the fetch fails. Raises only when BOTH sources fail."""
    try:
        feed = _fetch_feed()
        # The feed groups services under more than one top-level
        # list ("ais", "board", ...). Harvest every group that
        # carries a services list, whichever list it sits in.
        state = {}
        groups = []
        for value in feed.values():
            if isinstance(value, list):
                groups.extend(g for g in value if isinstance(g, dict))
        for group in groups:
            for svc in group.get("services", []) or []:
                if isinstance(svc, dict):
                    key = svc.get("key")
                    if key:
                        state[key] = bool(svc.get("up"))
        if state:
            return state, "feed"
    except Exception:
        pass
    with open(FALLBACK_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k): bool(v) for k, v in raw.items()}, "local-fallback"


def _report_line(service, was_up, is_up, up_count, total):
    """Echo's proactive line — assembly only, facts exact."""
    hhmm = _now_local_hhmm()
    if was_up and not is_up:
        return (f"House report: {service} went down at {hhmm}. "
                f"{up_count} of {total} services are up.")
    return (f"House report: {service} is back up at {hhmm}. "
            f"{up_count} of {total} services are up.")


def run_check():
    """Poll once. Returns the state map served, or None when stopped
    or when both sources failed. The first successful check only sets
    the baseline; flips against a known state are filed as reports."""
    global _state, _source, _last_check
    if _is_stopped_fn is not None and _is_stopped_fn():
        return None
    try:
        new_state, source = _read_source()
    except Exception:
        return None
    with _lock:
        previous = _state
        _state = new_state
        _source = source
        _last_check = datetime.now(timezone.utc).isoformat()
        if previous is None:
            return new_state
        up_count = sum(1 for v in new_state.values() if v)
        total = len(new_state)
        for service in sorted(set(previous) | set(new_state)):
            was = previous.get(service)
            now = new_state.get(service)
            if was is None or now is None or was == now:
                continue
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "service": service,
                "from": "up" if was else "down",
                "to": "up" if now else "down",
                "source": source,
            }
            try:
                with open(REPORTS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                pass
            _recent.append(entry)
            del _recent[:-50]
            _pending.append(
                _report_line(service, was, now, up_count, total))
            if _log_fn is not None:
                _log_fn("watchman_report", service=service,
                        **{"from": entry["from"], "to": entry["to"],
                           "source": source})
    return new_state


def _loop():
    while True:
        try:
            run_check()
        except Exception:
            pass
        time.sleep(_POLL)


def start(is_stopped_fn, log_fn=None):
    """Start the watcher thread. Called once by server.py at startup;
    is_stopped_fn is Echo's own is_stopped(), so STOP pauses the
    watcher through the same state as everything else."""
    global _started, _is_stopped_fn, _log_fn
    with _lock:
        if _started:
            return
        _started = True
        _is_stopped_fn = is_stopped_fn
        _log_fn = log_fn
        # Seed the recent-reports view from the file, if one exists.
        try:
            with open(REPORTS_FILE, encoding="utf-8") as f:
                lines = f.read().splitlines()
            for line in lines[-10:]:
                try:
                    _recent.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
    thread = threading.Thread(target=_loop, name="echo-watchman",
                              daemon=True)
    thread.start()
    if log_fn is not None:
        log_fn("watchman_start", feed=FEED_URL, interval=_POLL)


def take_pending_reports():
    """Drain the proactive queue. Each queued line is delivered once,
    with the next /chat reply, and never repeated."""
    with _lock:
        lines = list(_pending)
        del _pending[:]
        return lines


def is_house_question(text):
    lowered = text.lower()
    return any(p in lowered for p in HOUSE_QUESTION_PATTERNS)


def house_status_reply():
    """The assembled answer to a house-status question, or None when
    the watcher has no data yet (the caller then lets the brain
    answer as usual)."""
    with _lock:
        if _state is None:
            return None
        state = dict(_state)
        source = _source
        last_check = _last_check
    up_count = sum(1 for v in state.values() if v)
    total = len(state)
    line = f"House status: {up_count} of {total} services are up."
    down = sorted(k for k, v in state.items() if not v)
    if down:
        line += " Down right now: " + ", ".join(down) + "."
    else:
        line += " Everything is up."
    if last_check:
        try:
            when = datetime.fromisoformat(last_check)
            if _LOCAL_TZ:
                when = when.astimezone(_LOCAL_TZ)
            line += f" Last check {when.strftime('%H:%M')}."
        except Exception:
            pass
    if source:
        line += f" Source: {source}."
    return line


def status_payload(stopped):
    """The GET /watchman body."""
    with _lock:
        state = dict(_state) if _state is not None else {}
        source = _source
        last_check = _last_check
        recent = list(_recent[-10:])
        pending = len(_pending)
    payload = {
        "ok": True,
        "watching": not stopped,
        "source": source,
        "last_check": last_check,
        "current_state": state,
        "up_count": sum(1 for v in state.values() if v),
        "total": len(state),
        "recent_reports": recent,
        "pending_reports": pending,
    }
    if stopped:
        payload["reason"] = "stopped"
    return payload
