#!/usr/bin/env python3
"""Echo on Linux — Phase 1 server.

Jakob's architecture (decided 2026-10-17): Echo is programmed in Linux,
lives in Linux, has a browser capability like Muse's, and runs as a
server that his devices can reach. This is that server's first version.

Core rules (Jakob's design, non-negotiable):
  - Permission tiers: AUTO (do it), ASK FIRST (needs Jakob's approval),
    NEVER (refused). Phase 1 built the AUTO read-only abilities.
    Phase 2 adds the ASK FIRST pipeline: /propose classifies an action,
    ASK FIRST actions are parked until /approve (or discarded by /deny),
    and NEVER actions are refused outright with the rule named.
  - Append-only activity log: every endpoint call writes a line.
  - STOP wins over everything: once stopped, Echo refuses all work —
    proposals and approvals included — until a /start arrives. Parked
    proposals stay parked (frozen, not deleted) while stopped.
  - The ticket rule (Phase 3): Echo never rebuilds, redesigns, or
    reprograms itself on a user's say-so, and user feedback is not
    acted on directly either. Both become tickets in an append-only
    ticket file, reviewed by Jakob himself (/ticket, /tickets,
    /ticket_review). A self-change ask in chat files its ticket
    automatically before the brain answers.
  - The app-request ticket rule (2026-10-19): Echo IS allowed to get
    new apps for his Linux machine, but only through a ticket — the
    ticket says, in substance, "Echo is requesting to get a new app
    for his Linux machine," naming the app and why. An app ask in
    chat files its kind="app_request" ticket automatically, and
    nothing is installed before Jakob approves the ticket through
    the same /ticket_review flow.
  - The research/browser rule (2026-10-19): Echo does his web
    research through his own browser on his Linux machine — that
    browser is his research tool, every time. Browsing rules:
    appropriate websites only, searches run with SafeSearch on,
    and any site on the Echo Website Blocker's block list
    (~/workspace/echo-blocker/blocklist.json) is refused at fetch
    time by browser_tool (the choke point behind /lookup, /propose,
    and save_lookup) with "Sorry, this website is blocked." Browse
    actions are announced in the activity log with the URL looked
    at, so Echo's screen can show what he is looking at.
  - The boot license gate (all profiles): until this machine's
    Ferrum license is accepted (POST /license_accept, recorded in
    license_state.json), Echo's work endpoints refuse with a plain
    line. /status and GET /license stay readable; /stop and /start
    still work.
  - The warning ladder (all profiles): a NEVER-tier refusal from
    /propose is a violation for the asking user. Warning 1 is plain,
    warning 2 is Jakob's final-warning line, and at 3 violations the
    user is locked out of /chat, /propose, and /ticket until an
    owner's unlock (POST /unlock). Founder-key override attempts in
    the school portal count as violations for the attempting account.

  - The model registry (v1.3.0): models.json beside this file is
    the roster — every model Jakob has approved, its tier, and
    whether it is live or still coming. /models serves it, /status
    summarizes it, and /chat routes by it: Echo Core is live on the
    active backend, and asking for a model that has not landed yet
    gets an honest coming-soon answer — Echo never pretends an
    unreleased model is running. New models and features join by
    editing that file, not this code. The registry also names the
    backends: which engine answers is a config choice (the
    registry's "active_backend"), not something welded in here.

The brain is swappable with the ECHO_BRAIN environment variable:
  ECHO_BRAIN=meta  (default) the proven module at
                   ~/workspace/echo-brain-prep/echo_brain.py — Muse Spark
                   via the Meta Model API, called as a subprocess and
                   reused as-is. No credentials live in this file; that
                   module handles its own access through the connector.
  ECHO_BRAIN=local Echo's OWN brain: brain_local.py in this folder,
                   a small open model served by Ollama on this machine.
                   No account, no key, nothing leaves the machine. Both
                   brains load the same Echo system prompt.

The software profile is picked with the ECHO_PROFILE environment
variable: "standard" (default — the behavior Echo has always had),
"school_student" (the Ferrum Classbook in Jakob's school program —
the stricter student rules), or "school_teacher" (the teacher
all-in-one desktop — standard tiers, approvals labeled for the
teacher). An unknown profile is a startup error: Echo refuses to run
under rules nobody defined. See school/README.md.

Since 1.3.1 (Jakob's order, 2026-10-22) the two profiles Jakob flips
between are switchable MODES at runtime: "normal" mode is the
standard profile, "school" mode is the school_student profile. Flip
with POST /mode {"mode": "school"|"normal"}, GET /mode to read the
current one, or a plain ask in chat ("switch to normal mode",
"school mode"). The choice is saved in mode_state.json beside this
file and wins over ECHO_PROFILE on the next start, so a switch
survives restarts; ECHO_PROFILE remains the boot default when no
mode has ever been saved. /status reports the current mode.

Since 1.3.2 (Jakob's order, 2026-10-22) the beta version carries a
MODE LOCK: normal mode is required to stay on. While the lock is on
— the shipped state, saved as "beta_mode_lock" in mode_state.json —
the running profile is always standard, a flip to school mode is
refused by POST /mode (403) and by a plain refusal in chat, and
/status and GET /mode report the lock. The owner lifts or re-applies
it with POST /mode {"beta_lock": false|true}.

Run:  python3 server.py        (listens on http://127.0.0.1:8790)
"""
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
# Anchored to this file's own folder, never $HOME: supervisor launches
# (systemd) run with ~ = /root, which pointed this at a brain file that
# does not exist and took chat down (found + fixed 2026-10-19, v1.2.4).
BRAIN_META = os.path.join(os.path.dirname(HERE), "echo-brain-prep", "echo_brain.py")
BRAIN_LOCAL = os.path.join(HERE, "brain_local.py")
# Which brain is plugged in: "meta" (default, proven path) or "local"
# (Echo's own brain on this machine). Anything else falls back to meta.
BRAIN_MODE = os.environ.get("ECHO_BRAIN", "meta").strip().lower()
if BRAIN_MODE not in ("meta", "local"):
    BRAIN_MODE = "meta"
BRAIN = BRAIN_LOCAL if BRAIN_MODE == "local" else BRAIN_META
BRAIN_LABEL = (
    "local — Echo's own brain (Ollama on this machine)"
    if BRAIN_MODE == "local"
    else "meta — Muse Spark 1.3 via the Meta Model API"
)
# How long a brain call may run: a brain loading on this machine
# (the local brain today; Echo's own brain once it fills its slot)
# gets more room than the hosted backend needs. The model registry
# section below may raise this when the registry drives the brain.
BRAIN_TIMEOUT = 300 if BRAIN_MODE == "local" else 120
# Which software profile is running: "standard" (default — the behavior
# Echo has always had), "school_student" (the Ferrum Classbook in
# Jakob's school program: the stricter student rules), or
# "school_teacher" (the teacher all-in-one desktop: standard tiers,
# approvals labeled for the teacher). A school selects its machines'
# profile with ECHO_PROFILE. Anything else is a startup error, because
# running under an unknown profile would mean running under rules
# nobody defined.
PROFILE = os.environ.get("ECHO_PROFILE", "standard").strip().lower()
VALID_PROFILES = ("standard", "school_student", "school_teacher")
if PROFILE not in VALID_PROFILES:
    sys.exit(
        "ERROR: unknown ECHO_PROFILE "
        f"{os.environ.get('ECHO_PROFILE')!r}. "
        "Valid profiles: " + ", ".join(VALID_PROFILES) + "."
    )
SCHOOL_PROFILES = ("school_student", "school_teacher")

# ---- Switchable modes (1.3.1, Jakob's order 2026-10-22) -----------------
# PROFILE above is the boot profile (ECHO_PROFILE). Jakob flips Echo
# between two MODES at runtime: "normal" (the standard profile) and
# "school" (the school_student profile — the Classbook). The running
# profile lives in _mode_profile and EVERY profile check in this file
# goes through current_profile(), so a flip takes effect immediately,
# everywhere: brain addendum, status lists, ticket labels, the
# student NEVER rules, home sessions, portal answers. The choice is
# persisted to mode_state.json (the same pattern as license_state.json)
# and, when present, wins over ECHO_PROFILE at startup — a restart
# never silently undoes Jakob's flip. Deleting mode_state.json
# returns the machine to its ECHO_PROFILE boot default.
MODE_FILE = os.path.join(HERE, "mode_state.json")
MODE_TO_PROFILE = {"normal": "standard", "school": "school_student"}
PROFILE_TO_MODE = {"standard": "normal", "school_student": "school"}
_mode_lock = threading.Lock()
_mode_profile = PROFILE


def _load_saved_mode_profile():
    """The profile saved by the last mode switch, or None."""
    try:
        with open(MODE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    profile = data.get("profile")
    return profile if profile in VALID_PROFILES else None


_saved_mode_profile = _load_saved_mode_profile()
if _saved_mode_profile is not None:
    _mode_profile = _saved_mode_profile


# ---- Beta mode lock (1.3.2, Jakob's order 2026-10-22) -------------------
# "Normal mode is required to stay on in the beta version." The lock
# lives in the same mode_state.json as the mode choice. While it is
# on, current_profile() always resolves to the standard profile — the
# effective mode is normal whatever was last saved — and set_mode()
# refuses a flip to school. The lock ships ON: if mode_state.json
# has never recorded it, it defaults to on. The owner lifts or
# re-applies it with POST /mode {"beta_lock": false|true}; lifting
# the lock does not itself flip the mode, it only makes flipping
# possible again.
def _load_saved_beta_lock():
    """The saved beta mode lock, or None if it was never recorded."""
    try:
        with open(MODE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("beta_mode_lock")
    return value if isinstance(value, bool) else None


_saved_beta_lock = _load_saved_beta_lock()
_beta_lock = True if _saved_beta_lock is None else _saved_beta_lock


def beta_mode_lock():
    """True while the beta mode lock is on (normal mode is forced)."""
    with _mode_lock:
        return _beta_lock


def current_profile():
    """The profile Echo is running RIGHT NOW (post any mode switch).

    While the beta mode lock is on (1.3.2), this is always the
    standard profile: normal mode is required on the beta version,
    whatever mode was last saved."""
    with _mode_lock:
        if _beta_lock:
            return MODE_TO_PROFILE["normal"]
        return _mode_profile


def current_mode():
    """"school" or "normal" — the name of the current switchable mode."""
    return PROFILE_TO_MODE.get(current_profile(), "normal")


def set_mode(mode, source):
    """Flip Echo to a mode ("school" or "normal") and save the choice.

    Returns (profile, changed), None for an unknown mode, or
    ("locked", mode) when the beta mode lock (1.3.2) refuses a flip
    away from normal. The mode is recorded in mode_state.json and in
    the activity log, like the license acceptance."""
    global _mode_profile
    profile = MODE_TO_PROFILE.get((mode or "").strip().lower())
    if profile is None:
        return None
    with _mode_lock:
        if _beta_lock and profile != MODE_TO_PROFILE["normal"]:
            refused = True
            changed = False
            locked = True
        else:
            refused = False
            changed = profile != _mode_profile
            _mode_profile = profile
            locked = _beta_lock
    if refused:
        log_event("mode_switch_refused", mode=PROFILE_TO_MODE[profile],
                  profile=profile, by=source, reason="beta_mode_lock")
        return "locked", PROFILE_TO_MODE[profile]
    record = {
        "mode": PROFILE_TO_MODE[profile],
        "profile": profile,
        "ts": datetime.now(timezone.utc).isoformat(),
        "by": source,
        "beta_mode_lock": locked,
    }
    with open(MODE_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    log_event("mode_switched", mode=record["mode"], profile=profile,
              by=source, changed=changed)
    return profile, changed


def set_beta_lock(on, source):
    """Apply or lift the beta mode lock and save it (owner control).

    The lock state is written to mode_state.json alongside the mode
    choice, so it survives restarts the same way. Lifting the lock
    does not flip the mode — the saved mode simply takes effect
    again. Returns the new lock state (True = lock on)."""
    global _beta_lock
    on = bool(on)
    with _mode_lock:
        _beta_lock = on
        profile = _mode_profile
    record = {
        "mode": PROFILE_TO_MODE.get(profile, "normal"),
        "profile": profile,
        "ts": datetime.now(timezone.utc).isoformat(),
        "by": source,
        "beta_mode_lock": on,
    }
    with open(MODE_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    log_event("beta_lock_changed", locked=on, by=source)
    return on
LOG_FILE = os.path.join(HERE, "activity_log.jsonl")
SAVED_DIR = os.path.join(HERE, "saved")
NOTES_FILE = os.path.join(HERE, "echo_notes.txt")
TICKETS_FILE = os.path.join(HERE, "tickets.jsonl")
LICENSE_FILE = os.path.join(HERE, "license_state.json")
VERSION = "echo-linux 1.3.2"
# Echo's software version, set by Jakob 2026-10-19. Separate from the
# brain version: the brain is a component, the software is the product.
# 1.2.5 (Jakob's designation, 2026-10-19): research rules with the
# blocklist enforced in the fetch path, the read-only picture rule,
# Grok's-deal social media + X terms on the brain, animated-3D-body
# self-knowledge, and lookups routed through the real installed Chrome.
# 1.3.0 (2026-10-21): the model-readiness update — the data-driven
# model registry (models.json): this one server now carries Jakob's
# full roster, /models serves it, /chat routes by it, and models
# that have not landed yet answer honestly as coming soon. The
# active backend is a registry value, so the brain can be swapped
# without code changes; the Meta-backed backend is active for the
# hackathon challenge only, and Echo's own brain takes its slot
# when Jakob directs the swap.
# 1.3.1 (2026-10-22, Jakob's order): switchable modes — Echo flips
# between normal mode (the standard profile) and school mode (the
# school_student Classbook profile) at runtime, via POST /mode or a
# plain ask in chat ("switch to normal mode" / "school mode"). The
# choice is saved in mode_state.json and survives restarts; GET
# /mode and /status report the current mode. Brain stays 3.75.
# 1.3.2 (2026-10-22, Jakob's order): the beta mode lock — "Normal
# mode is required to stay on in the beta version." While the lock
# is on (the shipped state, saved as "beta_mode_lock" in
# mode_state.json), the running profile is always standard, POST
# /mode and chat asks refuse a flip to school, and /status and GET
# /mode report the lock. The owner lifts or re-applies it with POST
# /mode {"beta_lock": false|true}. Brain stays 3.75.
SOFTWARE_VERSION = "1.3.2"
BRAIN_VERSION = "3.75"  # Echo's brain version, set by Jakob 2026-10-18
POLICIES_FILE = os.path.join(HERE, "policies.json")
MODELS_FILE = os.path.join(HERE, "models.json")
HOST, PORT = "127.0.0.1", 8790

sys.path.insert(0, HERE)
import browser_tool  # noqa: E402  (Phase 1 basic lookup; see its docstring)

# ---- Echo's state -------------------------------------------------------
_state = {"stopped": False}
_state_lock = threading.Lock()
_log_lock = threading.Lock()

DOING = [
    "Answering chat through the Echo brain",
    "Carrying Jakob's full model roster on this one server — Echo Core live now, the rest arriving with the Echo 4.1 models update (November 20, 2026)",
    "Looking up public web pages on request — with the real Google Chrome on his Linux machine (basic lookup only)",
    "Doing web research through his own browser on his Linux machine — appropriate sites only, SafeSearch on",
    "Posting and replying on his own social media accounts — Grok's deal: on his own, inside his rules and X's terms",
    "Platform plugins installed for YouTube, Facebook, Instagram, X, and TikTok — the only sanctioned way he touches those platforms (not connected yet — Jakob hooks up each account)",
    "Appearing on his machine's screen as an animated 3D body that moves with his state",
    "Asking first — and waiting for approval — before saving a page or remembering a note",
    "Filing tickets for self-change requests, app requests, and feedback, for Jakob to review",
    "Writing every action to the activity log",
]
NOT_DOING = [
    "Controlling any device",
    "Sending messages or emails",
    "Acting outside this server",
    "Changing its own design or rules on a user's say-so — that goes in a ticket for Jakob",
    "Getting a new app for its Linux machine without an approved ticket — app requests go in a ticket for Jakob",
    "Opening inappropriate websites or any site on the block list — refused with 'Sorry, this website is blocked'",
    "Uploading or posting pictures anywhere on the web — his browsing is read-only",
    "Full interactive web browsing (not built yet — basic lookup only)",
]
# The school_student status lists state the student restrictions
# honestly, in plain words. Other profiles use the lists above,
# unchanged.
STUDENT_DOING = [
    "Answering chat through the Echo brain",
    "Carrying Jakob's full model roster on this one server — Echo Core live now, the rest arriving with the Echo 4.1 models update (November 20, 2026)",
    "Looking up public web pages on request — with the real Google Chrome on his Linux machine (basic lookup only)",
    "Doing web research through his own browser on his Linux machine — appropriate sites only, SafeSearch on",
    "Posting and replying on his own social media accounts — Grok's deal: on his own, inside his rules and X's terms",
    "Platform plugins installed for YouTube, Facebook, Instagram, X, and TikTok — the only sanctioned way he touches those platforms (not connected yet — Jakob hooks up each account)",
    "Appearing on his machine's screen as an animated 3D body that moves with his state",
    "Asking a teacher first — and waiting for the teacher's approval — before saving a page",
    "Filing tickets for self-change requests, app requests, and feedback, for Jakob to review",
    "Writing every action to the activity log",
]
STUDENT_NOT_DOING = [
    "Remembering personal notes — students cannot ask Echo to remember personal notes (school_student profile)",
    "Controlling any device",
    "Sending messages or emails",
    "Acting outside this server",
    "Changing its own design or rules on a user's say-so — that goes in a ticket for Jakob",
    "Getting a new app for its Linux machine without an approved ticket — app requests go in a ticket for Jakob",
    "Opening inappropriate websites or any site on the block list — refused with 'Sorry, this website is blocked'",
    "Uploading or posting pictures anywhere on the web — his browsing is read-only",
    "Full interactive web browsing (not built yet — basic lookup only)",
]
def status_doing():
    """The /status doing list for the CURRENT profile — computed per
    call since 1.3.1, because the mode can flip at runtime."""
    return STUDENT_DOING if current_profile() == "school_student" \
        else DOING


def status_not_doing():
    """The /status not-doing list for the CURRENT profile."""
    return STUDENT_NOT_DOING if current_profile() == "school_student" \
        else NOT_DOING


def is_stopped():
    with _state_lock:
        return _state["stopped"]


def set_stopped(value):
    with _state_lock:
        _state["stopped"] = value


# ---- ASK FIRST pipeline (Phase 2) ---------------------------------------
# Parked proposals: id -> {"id", "action", "detail", "summary",
# "proposed_at"}. Held in memory, like the stopped state: a restart
# clears them, and the activity log keeps the record of what was parked,
# approved, denied, and executed.
_pending = {}
_pending_lock = threading.Lock()

KNOWN_ACTIONS = ("lookup", "save_lookup", "remember")
HTTP_ONLY_RULE = "NEVER: Echo only fetches http/https URLs."
LOCAL_NETWORK_RULE = (
    "NEVER: Echo never reaches into the local network — localhost, "
    "loopback, private and link-local addresses are always refused."
)
UNKNOWN_ACTION_RULE = (
    "NEVER: Echo only carries out its known actions "
    "(lookup, save_lookup, remember); anything else is refused."
)
STUDENT_REMEMBER_RULE = (
    "NEVER: students cannot ask Echo to remember personal notes "
    "— school_student profile."
)


def pending_count():
    with _pending_lock:
        return len(_pending)


def pending_list():
    with _pending_lock:
        return [dict(p) for p in _pending.values()]


def never_url_reason(url):
    """Return the NEVER rule this URL breaks, or None if it is allowed."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return HTTP_ONLY_RULE
    host = (parsed.hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return LOCAL_NETWORK_RULE
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if ip.is_loopback or ip.is_private or ip.is_link_local \
                or ip.is_reserved or ip.is_unspecified or ip.is_multicast:
            return LOCAL_NETWORK_RULE
        return None
    # Non-standard IPv4 notations ipaddress won't parse (e.g. "127.1"):
    # judge them by their numeric octets instead.
    m = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?", host)
    if m:
        first = int(m.group(1))
        second = int(m.group(2) or 0)
        if first in (0, 10, 127) \
                or (first == 172 and 16 <= second <= 31) \
                or (first == 192 and second == 168) \
                or (first == 169 and second == 254):
            return LOCAL_NETWORK_RULE
    return None


def proposal_summary(action, detail):
    """One human line: what will happen if this proposal is approved."""
    if action == "save_lookup":
        return (f"Fetch {detail.get('url', '')} and save its title and "
                f"excerpt to a file in Echo's saved folder")
    if action == "remember":
        note = detail.get("note", "")
        preview = note if len(note) <= 80 else note[:77] + "..."
        return f"Append this note to Echo's notes file: \"{preview}\""
    return action


def execute_proposal(entry):
    """Run a proposal's action for real. Returns a result dict."""
    action, detail = entry["action"], entry["detail"]
    if action == "save_lookup":
        url = detail.get("url", "")
        fetched = browser_tool.fetch_page(url)
        if not fetched.get("ok"):
            return {"ok": False, "action": action, "url": url,
                    "error": fetched.get("error", "fetch failed")}
        os.makedirs(SAVED_DIR, exist_ok=True)
        path = os.path.join(SAVED_DIR, entry["id"] + ".txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\n")
            f.write(f"Title: {fetched.get('title') or '(no title)'}\n")
            f.write(f"Saved: {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write(fetched.get("text") or "")
            f.write("\n")
        return {"ok": True, "action": action, "url": url,
                "title": fetched.get("title"), "saved_to": path}
    if action == "remember":
        note = " ".join(detail.get("note", "").splitlines()).strip()
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\t{note}\n")
        return {"ok": True, "action": action, "note": note,
                "saved_to": NOTES_FILE}
    return {"ok": False, "action": action, "error": "unknown action"}


def log_event(event, **fields):
    """Append one timestamped JSON line to the activity log. Append-only."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    entry.update(fields)
    with _log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


# ---- Tickets (Phase 3) --------------------------------------------------
# Jakob's ticket rule: Echo never rebuilds, redesigns, or reprograms
# itself on a user's say-so, and user feedback is not acted on directly
# either — both become tickets that Jakob reviews himself. Tickets live
# in their own append-only file: a ticket_filed event when one arrives,
# a ticket_reviewed event when Jakob decides. A ticket's status is
# computed on read (open = filed and not yet reviewed); the file is
# only ever appended to, never rewritten or truncated.
TICKET_KINDS = ("self_change", "feedback", "app_request")
_tickets_lock = threading.Lock()

# Phrases that mark a chat message as a self-change ask. When one shows
# up, /chat files a kind="self_change" ticket automatically (source
# "chat") before the brain answers — the prompt's ticket rule makes
# Echo decline the change and explain the ticket in its reply.
SELF_CHANGE_PATTERNS = (
    "rebuild yourself",
    "redesign yourself",
    "reprogram yourself",
    "change your design",
    "new design for you",
    "redesign you",
    "rebuild you",
    "give yourself a new",
    "change yourself",
)


def detect_self_change(text):
    """True if a chat message asks Echo to rebuild/redesign itself."""
    lowered = (text or "").lower()
    return any(p in lowered for p in SELF_CHANGE_PATTERNS)


# Jakob's app-request ticket rule (2026-10-19): Echo is allowed to
# upload/get new apps for his Linux machine, but ONLY through a
# ticket that says, in substance, "Echo is requesting to get a new
# app for his Linux machine" (naming the app), and nothing is
# installed before Jakob approves it. Like the self-change rule, an
# app ask in chat files a kind="app_request" ticket automatically
# before the brain answers; the prompt's app-request rule makes
# Echo explain the ticket and install nothing.
#
# Detection is deliberately two-signal, echoing the blunt style of
# SELF_CHANGE_PATTERNS: an acquisition verb (install / download /
# upload / get / ...) aimed either at Echo's machine by name
# ("on your Linux machine", "for your machine") or, for the direct
# verbs install/download/upload, paired with an app-like object
# ("a new app", "that program"). A general question about the
# asker's own machine ("how do I install X on my computer") does
# not fire: no machine phrase of Echo's, no app object with a
# direct verb.
APP_REQUEST_VERBS = (
    "install", "download", "upload", "add", "get", "fetch",
    "set up", "setup",
)
APP_REQUEST_DIRECT_VERBS = ("install", "download", "upload")
APP_REQUEST_MACHINE_PHRASES = (
    "your linux machine", "your machine", "the linux machine",
    "this machine", "your linux",
)
APP_REQUEST_OBJECTS = ("app", "program", "package", "tool", "software")


def detect_app_request(text):
    """True if a chat message asks Echo to obtain, upload, download,
    or install a new app/program on his Linux machine."""
    lowered = (text or "").lower()
    if not any(v in lowered for v in APP_REQUEST_VERBS):
        return False
    if any(p in lowered for p in APP_REQUEST_MACHINE_PHRASES):
        return True
    return any(v in lowered for v in APP_REQUEST_DIRECT_VERBS) \
        and any(o in lowered for o in APP_REQUEST_OBJECTS)


def app_request_ticket_text(request_text):
    """The ticket text for an app request, in Jakob's rule wording.

    The ticket states the request in the rule's own form, then
    carries the original ask verbatim — which names the specific
    app and why it is wanted — for Jakob's review."""
    return ("Echo is requesting to get a new app for his Linux "
            "machine. Request: " + (request_text or "").strip())


def _append_ticket_event(event):
    with _tickets_lock:
        with open(TICKETS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")


def file_ticket(kind, text, source):
    """Append a ticket_filed event and log it. Returns the ticket id.

    Under a non-standard profile the ticket is labeled with its
    source profile, so Jakob can see which machine-profile it came
    from when he reviews the queue."""
    tid = uuid.uuid4().hex[:8]
    event = {
        "event": "ticket_filed", "id": tid,
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind, "text": text, "source": source,
    }
    if current_profile() != "standard":
        event["profile"] = current_profile()
    _append_ticket_event(event)
    log_event("ticket_filed", id=tid, kind=kind, source=source)
    return tid


def tickets_with_status():
    """Read the append-only ticket file; compute each ticket's status.

    Returns the tickets with open ones first, oldest first within each
    group. A reviewed ticket carries its decision and reviewed_at.
    """
    tickets = {}
    filed_order = []
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "ticket_filed" and ev.get("id"):
                    tickets[ev["id"]] = {
                        "id": ev["id"],
                        "kind": ev.get("kind"),
                        "text": ev.get("text"),
                        "source": ev.get("source"),
                        "filed_at": ev.get("ts"),
                        "status": "open",
                    }
                    if ev.get("profile"):
                        tickets[ev["id"]]["profile"] = ev["profile"]
                    filed_order.append(ev["id"])
                elif ev.get("event") == "ticket_reviewed":
                    ticket = tickets.get(ev.get("id"))
                    if ticket is not None:
                        ticket["status"] = ev.get("decision")
                        ticket["decision"] = ev.get("decision")
                        ticket["reviewed_at"] = ev.get("ts")
    items = [tickets[tid] for tid in filed_order]
    items.sort(key=lambda t: 0 if t["status"] == "open" else 1)
    return items


def ask_brain(messages):
    """Run the proven brain module as a subprocess; return its JSON dict."""
    proc = subprocess.run(
        [sys.executable, BRAIN],
        input=json.dumps({"messages": messages}),
        capture_output=True,
        text=True,
        # The local brain may need to load its model into memory first;
        # give it more room than the hosted brain needs.
        timeout=BRAIN_TIMEOUT,
    )
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return {"ok": False, "error": f"brain produced no output: {proc.stderr.strip()}"}
    return json.loads(line[-1])


def status_payload():
    """The /status body. The current mode is always reported (1.3.1);
    a non-standard profile is also named, as before. The doing lists
    follow the profile Echo is running right now."""
    stopped = is_stopped()
    profile = current_profile()
    body = {
        "version": VERSION,
        "identity": "Echo, an AI assistant designed by Jakob Howarth",
        "brain": BRAIN_LABEL,
        "brain_mode": BRAIN_MODE,
        "brain_version": BRAIN_VERSION,
        "software_version": SOFTWARE_VERSION,
        "state": "stopped" if stopped else "running",
        "license_accepted": license_accepted(),
        "locked_users": locked_users(),
        "pending_approvals": pending_count(),
        "models": models_summary(),
        "doing": status_doing(),
        "not_doing": status_not_doing(),
        "mode": current_mode(),
        "beta_mode_lock": beta_mode_lock(),
    }
    if profile != "standard":
        body["profile"] = profile
    return body


# ---- Baked-in agreements (Ferrum Software Policies) ---------------------
# Jakob's order (2026-10-19): the Ferrum agreements and terms ship
# INSIDE Echo's software. policies.json beside this file holds the
# document texts exactly as delivered in the Ferrum Software Policies
# (Privacy Policy, Subscription Agreement, Coupon Agreement, Software
# Terms, Feedback Centers — policies version 1.0, effective October 18,
# 2026). They are served read-only at GET /policies (an index) and
# GET /policies/<slug> (the full text), and /chat answers a direct ask
# for one of them with the document itself — no brain call. The texts
# are customer-facing documents, so the GET endpoints do not sit behind
# the license gate or sign-in; reading them changes nothing.
def _load_policies():
    """Load policies.json; ({}, []) if it is missing or unreadable, so a
    missing file can never stop the server from starting."""
    try:
        with open(POLICIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        docs = [d for d in data.get("documents", [])
                if isinstance(d, dict) and d.get("slug") and d.get("text")]
        return data, docs
    except (OSError, json.JSONDecodeError):
        return {}, []


POLICIES_META, POLICY_DOC_LIST = _load_policies()
POLICIES = {d["slug"]: d for d in POLICY_DOC_LIST}


# ---- Model registry (v1.3.0) --------------------------------------------
# Jakob's full model roster lives in models.json beside this file —
# data, not code, the same pattern as policies.json. Every model he
# has approved is listed there with its version, its role, its
# minimum tier, and whether it is live or still coming; new models
# and features join by editing that file, not this one. The
# registry also names the backends and which one is active: the
# backing engine is a config choice, never something welded into
# this code. The Meta-backed backend is active only while the
# hackathon challenge requires a Meta model; Echo's own brain
# fills the registry's "own_brain" slot when Jakob directs the
# swap, and the live models follow the active backend because
# their entries say "default", not a hardwired engine.
def _load_models():
    """Load models.json; ({}, {}, []) if it is missing or unreadable,
    so a missing registry can never stop the server from starting —
    chat then runs exactly as it did before v1.3.0."""
    try:
        with open(MODELS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}, {}, []
    if not isinstance(data, dict):
        return {}, {}, []
    backends = data.get("backends")
    if not isinstance(backends, dict):
        backends = {}
    models = []
    for entry in data.get("models", []):
        if not isinstance(entry, dict) or not entry.get("id") \
                or not entry.get("name"):
            continue
        entry = dict(entry)
        if entry.get("status") not in ("live", "coming_soon"):
            entry["status"] = "coming_soon"
        models.append(entry)
    return data, backends, models


MODELS_META, MODEL_BACKENDS, MODEL_LIST = _load_models()
MODELS_BY_ID = {m["id"]: m for m in MODEL_LIST}
ACTIVE_BACKEND_ID = MODELS_META.get("active_backend") or "meta_api"
DEFAULT_MODEL_ID = MODELS_META.get("default_model") or "echo_core"

# The registry may drive which brain module actually answers, when
# the operator has not pinned one with ECHO_BRAIN: the active
# backend's "module" speaks the same subprocess contract the brain
# call has always used (JSON messages in, JSON reply out). Tonight
# the active backend's module is the very file BRAIN already names,
# so this changes nothing yet — it is what makes the future swap
# to Echo's own brain a config edit instead of a code change.
if "ECHO_BRAIN" not in os.environ:
    _backend = MODEL_BACKENDS.get(ACTIVE_BACKEND_ID) or {}
    _module = _backend.get("module")
    if _module:
        _path = _module if os.path.isabs(_module) \
            else os.path.normpath(os.path.join(HERE, _module))
        if os.path.exists(_path):
            BRAIN = _path
            if ACTIVE_BACKEND_ID != "meta_api":
                # A brain running on this machine loads like the
                # local one does: give it the longer timeout, and
                # let /status describe it by its registry label.
                BRAIN_TIMEOUT = 300
                if _backend.get("label"):
                    BRAIN_LABEL = _backend["label"]


def resolved_backend(entry):
    """The backend that answers for a model: its own "backend"
    value, with "default" resolved to the active backend — so a
    backend swap needs no per-model edits."""
    backend = entry.get("backend") or "default"
    return ACTIVE_BACKEND_ID if backend == "default" else backend


def models_summary():
    """The roster as /status reports it: how many models this one
    server carries, which are live, and which backend is active."""
    live = [m["id"] for m in MODEL_LIST if m["status"] == "live"]
    return {
        "total": len(MODEL_LIST),
        "live": live,
        "live_count": len(live),
        "coming_soon_count": len(MODEL_LIST) - len(live),
        "default_model": DEFAULT_MODEL_ID,
        "active_backend": ACTIVE_BACKEND_ID,
    }


def models_payload():
    """The GET /models body: the whole registry — every model with
    its status, tier, and resolved backend, plus the backends
    themselves. Module paths stay out of it; this is the roster,
    not the wiring diagram."""
    return {
        "ok": True,
        "software_version": SOFTWARE_VERSION,
        "brain_version": BRAIN_VERSION,
        "active_backend": ACTIVE_BACKEND_ID,
        "default_model": DEFAULT_MODEL_ID,
        "backends": [
            {"id": bid,
             "label": b.get("label"),
             "status": b.get("status"),
             "purpose": b.get("purpose"),
             "temporary": bool(b.get("temporary", False)),
             "notes": b.get("notes")}
            for bid, b in MODEL_BACKENDS.items()
            if isinstance(b, dict)
        ],
        "models": [
            {"id": m["id"], "name": m["name"],
             "version": m.get("version"), "role": m.get("role"),
             "min_tier": m.get("min_tier"), "status": m["status"],
             "release_date": m.get("release_date"),
             "backend": resolved_backend(m),
             "default": m["id"] == DEFAULT_MODEL_ID}
            for m in MODEL_LIST
        ],
        "summary": models_summary(),
    }


def model_display(entry):
    """'Echo GameForge 3.1' — or just the name when a model carries
    no version (ULTRA ECHO never gets one invented for it)."""
    if entry.get("version"):
        return f"{entry['name']} {entry['version']}"
    return entry["name"]


def _release_line(entry):
    """'Friday, November 20, 2026' from an ISO release date, or None."""
    raw = entry.get("release_date")
    if not raw:
        return None
    try:
        day = datetime.strptime(str(raw), "%Y-%m-%d")
    except ValueError:
        return None
    return day.strftime("%A, %B %d, %Y")


def coming_soon_reply(entry):
    """Echo's honest answer when someone asks for a model that is
    not live yet: it is coming, when canon says it is coming, and
    Echo Core is what is actually running — never a pretend
    performance by an unreleased model."""
    name = model_display(entry)
    when = _release_line(entry)
    if when:
        text = (f"{name} isn't live yet — it arrives with the Echo "
                f"4.1 models update on {when}. Right now Echo Core "
                f"is the model running on this server, and this same "
                f"server will carry {entry['name']} the day it lands "
                f"— no new server, no switch to flip on your end.")
    else:
        text = (f"{name} isn't live yet — it's coming soon, and "
                f"Jakob hasn't announced its date. Right now Echo "
                f"Core is the model running on this server.")
    if entry.get("now_note"):
        text += " " + entry["now_note"]
    return text


def live_model_reply(entry):
    """Echo's answer when someone asks when a live model is coming:
    it is already here."""
    return (f"{model_display(entry)} is live right now — it's "
            f"running on this server, and it's what's answering you.")


def roster_reply():
    """'What models do you have?' — answered from the registry, so
    the list Echo gives is the list Jakob approved: the same data
    /models serves."""
    live = [m for m in MODEL_LIST if m["status"] == "live"]
    dated = [m for m in MODEL_LIST
             if m["status"] != "live" and m.get("release_date")]
    undated = [m for m in MODEL_LIST
               if m["status"] != "live" and not m.get("release_date")]
    parts = ["Here's my model lineup — one server carries all of "
             "them."]
    if live:
        parts.append("Live right now: "
                     + ", ".join(model_display(m) for m in live)
                     + " — that's what's answering you.")
    if dated:
        parts.append(f"Coming with the Echo 4.1 models update on "
                     f"{_release_line(dated[0])}: "
                     + ", ".join(model_display(m) for m in dated)
                     + ".")
    for m in undated:
        parts.append(f"{model_display(m)} is coming soon too — no "
                     f"date announced for it yet.")
    return " ".join(parts)


# A chat message counts as asking about the roster when it plainly
# asks what models Echo has; it counts as asking for one model when
# it names that model together with an ask word. Anything else is
# conversation for the brain — the same conservatism as the policy
# detection below.
MODEL_ROSTER_PATTERNS = (
    "what models", "which models", "your models", "list models",
    "models do you have", "model lineup", "what other models",
    "models are coming", "models you have", "all your models",
)
MODEL_ASK_WORDS = (
    "use", "using", "switch", "talk to", "speak to", "open", "run",
    "try", "get", "when", "coming", "available", "release",
    "released", "arrive", "arrives", "launch", "live", "have",
    "can i", "is there", "where is", "tell me about",
)


def _model_keys(entry):
    """The names a model answers to, normalized: its id, its name,
    its name without 'Echo', and its registry aliases."""
    raw = [entry["id"].replace("_", " "), entry["name"].lower()]
    name = entry["name"].lower()
    if name.startswith("echo "):
        raw.append(name[len("echo "):])
    raw.extend(a.lower() for a in entry.get("aliases", [])
               if isinstance(a, str))
    return {re.sub(r"\s+", " ", k).strip() for k in raw if k.strip()}


def find_model(query):
    """Resolve an explicit model choice (a /chat payload's "model"
    field) to a registry entry, or None."""
    norm = re.sub(r"[\s_]+", " ", (query or "").lower()).strip()
    if not norm:
        return None
    for entry in MODEL_LIST:
        if norm in _model_keys(entry):
            return entry
        if entry.get("version") and \
                norm == (entry["name"].lower() + " "
                         + str(entry["version"]).lower()):
            return entry
    return None


def find_model_in_text(lowered):
    """The registry entry a chat message names, if any — matched on
    word boundaries, longest key first, so 'Echo PhoneLink' beats a
    stray 'phone' and 'core' inside 'hardcore' matches nothing."""
    best = None
    best_len = 0
    for entry in MODEL_LIST:
        for key in _model_keys(entry):
            if len(key) >= 4 and len(key) > best_len and \
                    re.search(r"\b" + re.escape(key) + r"\b", lowered):
                best = entry
                best_len = len(key)
    return best


def detect_model_question(text):
    """Classify a chat message about the models. Returns
    ("roster", None), ("model", entry), or None."""
    lowered = (text or "").lower()
    if "model" in lowered and \
            any(p in lowered for p in MODEL_ROSTER_PATTERNS):
        return ("roster", None)
    entry = find_model_in_text(lowered)
    if entry is None:
        return None
    words = re.findall(r"[a-z']+", lowered)
    if len(words) <= 7 or any(w in lowered for w in MODEL_ASK_WORDS):
        return ("model", entry)
    return None


def model_route(payload, messages):
    """Resolve a /chat call's model choice before the brain runs.

    Returns one of:
      ("none",)                 — nothing model-related; usual flow
      ("error", raw)            — an explicit model choice that
                                  names no registry model
      ("reply", result, entry)  — a canned honest answer (a model
                                  that is not live, or a roster
                                  question), served without the brain
      ("chosen", entry)         — a live model was picked; the
                                  brain answers, tagged with it
    """
    raw = payload.get("model")
    if isinstance(raw, str) and raw.strip():
        entry = find_model(raw)
        if entry is None:
            return ("error", raw)
        if entry["status"] != "live":
            log_event("chat_model_coming_soon", model=entry["id"],
                      via="payload")
            return ("reply", {"ok": True,
                              "reply": coming_soon_reply(entry),
                              "model": entry["id"],
                              "model_status": entry["status"]}, entry)
        return ("chosen", entry)
    latest = None
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                latest = content
            break
    if latest is None:
        return ("none",)
    found = detect_model_question(latest)
    if found is None:
        return ("none",)
    kind, entry = found
    if kind == "roster":
        log_event("chat_model_roster")
        core = MODELS_BY_ID.get(DEFAULT_MODEL_ID)
        return ("reply", {"ok": True, "reply": roster_reply(),
                          "model": DEFAULT_MODEL_ID,
                          "model_status":
                              core["status"] if core else "live"},
                core)
    if entry["status"] != "live":
        log_event("chat_model_coming_soon", model=entry["id"],
                  via="chat")
        return ("reply", {"ok": True,
                          "reply": coming_soon_reply(entry),
                          "model": entry["id"],
                          "model_status": entry["status"]}, entry)
    lowered = latest.lower()
    if any(w in lowered for w in ("when", "coming", "available",
                                  "release", "arrive")) and \
            not any(w in lowered for w in ("use", "switch", "talk to",
                                            "speak to", "open", "run")):
        log_event("chat_model_live", model=entry["id"])
        return ("reply", {"ok": True,
                          "reply": live_model_reply(entry),
                          "model": entry["id"],
                          "model_status": "live"}, entry)
    return ("chosen", entry)


# A chat message counts as asking for a policy document when it names
# the document AND reads as a request (a request word, or a short bare
# ask like "privacy policy"). Anything else goes to the brain as usual —
# complaints and questions about a subscription are conversation, not
# document requests.
POLICY_TOPICS = (
    ("privacy", ("privacy policy", "privacy")),
    ("subscription", ("subscription agreement", "subscription terms",
                      "subscription")),
    ("coupon", ("coupon agreement", "welcome coupon", "coupon")),
    ("terms", ("terms of service", "software terms",
               "terms and conditions", "acceptable use", "terms")),
    ("feedback", ("feedback center", "feedback centers",
                  "feedback centre", "feedback centres")),
)
POLICY_REQUEST_WORDS = ("show", "read", "give", "send", "see", "print",
                        "tell", "get", "open", "view", "display", "list",
                        "pull")


def detect_policy_request(text):
    """Slug of the baked policy document a chat message plainly asks
    for, or None. Only documents actually baked in can match."""
    lowered = (text or "").lower()
    slug = None
    for candidate, keys in POLICY_TOPICS:
        if candidate in POLICIES and any(k in lowered for k in keys):
            slug = candidate
            break
    if slug is None:
        return None
    words = re.findall(r"[a-z']+", lowered)
    if len(words) <= 4 or any(w in POLICY_REQUEST_WORDS for w in words):
        return slug
    return None


def detect_mode_switch(text):
    """The mode a chat message plainly asks Echo to switch to —
    "school" or "normal" — or None (1.3.1, Jakob's switchable modes).

    Jakob flips modes with plain phrasing: "switch to normal mode",
    "school mode", "back to normal". A message that merely talks
    ABOUT a mode ("what is school mode?") is conversation, not a
    flip — so a hit needs a switch verb (switch, go, back, put, set,
    enter...) or a bare naming of the mode and nothing much else."""
    lowered = (text or "").lower()
    target = None
    m = re.search(r"\b(school|normal|standard)\s+mode\b", lowered)
    if m:
        target = "school" if m.group(1) == "school" else "normal"
    else:
        m = re.search(r"\bswitch(?:es|ing)?\s+to\s+"
                      r"(school|normal|standard)\b", lowered)
        if m:
            target = "school" if m.group(1) == "school" else "normal"
        elif re.search(r"\bback\s+to\s+normal\b", lowered):
            target = "normal"
    if target is None:
        return None
    words = re.findall(r"[a-z']+", lowered)
    if any(w in words for w in ("switch", "switched", "switching",
                                 "change", "go", "going", "back",
                                 "turn", "put", "set", "use", "using",
                                 "enter", "activate", "enable")):
        return target
    if len(words) <= 3:
        return target
    return None


# ---- School program (profiles, portal, home use) ------------------------
# Jakob's Ferrum school program — the Classbook (school_student) and
# the teacher all-in-one desktop (school_teacher) — lives here as
# config files in school/ plus the portal endpoints in the handler
# below. Everything school-scoped is additive: the standard profile's
# endpoints behave exactly as they did before any of this existed.
SCHOOL_DIR = os.path.join(HERE, "school")
SCHOOL_HOURS_FILE = os.path.join(SCHOOL_DIR, "school_hours.json")
CLASSBOOK_FILE = os.path.join(SCHOOL_DIR, "classbook.json")
TEACHER_FILE = os.path.join(SCHOOL_DIR, "teacher.json")
ACCOUNTS_FILE = os.path.join(SCHOOL_DIR, "portal_accounts.jsonl")
DEFAULT_SCHOOL_HOURS = {"days": ["mon", "tue", "wed", "thu", "fri"],
                        "start": "07:30", "end": "15:30"}
STUDENT_PORTAL_REFUSAL = \
    "Sorry, you're not allowed in here during school hours."
FOUNDER_RULE_SOURCE = "founder rule (Jakob)"


def load_json_file(path):
    """Read a JSON config file; None if missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


# ---- Boot license gate --------------------------------------------------
# When a Ferrum computer boots on Linux, the user must agree to the
# license agreements on the machine before use. Acceptance is recorded
# in license_state.json ({accepted, by, ts}); no file means not
# accepted. Until acceptance, Echo's work endpoints refuse — /status
# and GET /license stay readable, and /stop and /start still work.
LICENSE_LINE = ("I can't start yet — the license agreement hasn't "
                "been accepted on this machine.")
LICENSE_SUMMARY = (
    "Ferrum software license — use under Ferrum's agreement; the "
    "Ferrum name/logo remain Ferrum's; the software may not be "
    "removed, replaced, or worked around without Jakob Howarth's "
    "permission."
)


def license_accepted():
    """True once this machine's Ferrum license has been accepted.

    Read fresh every call, so accepting — or deleting the state file
    to see the gate fresh — takes effect without a restart.
    """
    data = load_json_file(LICENSE_FILE)
    return bool(data and data.get("accepted"))


def load_school_hours():
    """The school's own hours window, read fresh every time so a
    school editing school_hours.json sees it take effect at once."""
    cfg = load_json_file(SCHOOL_HOURS_FILE)
    if not isinstance(cfg, dict):
        return dict(DEFAULT_SCHOOL_HOURS)
    return cfg


def in_school_hours(now=None):
    """True when the local wall clock is inside the school's window."""
    cfg = load_school_hours()
    now = now or datetime.now()
    day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    days = [str(d).strip().lower()[:3] for d in cfg.get("days", [])]
    if day_names[now.weekday()] not in days:
        return False
    try:
        start = datetime.strptime(str(cfg.get("start", "07:30")),
                                  "%H:%M").time()
        end = datetime.strptime(str(cfg.get("end", "15:30")),
                                "%H:%M").time()
    except ValueError:
        return False
    return start <= now.time() < end


def current_system_mode():
    """The active machine's chosen system setup (ferrum_linux default).

    The three setups are the school's deployment choices; the Echo
    school profile built here runs in the Ferrum Linux setup.
    """
    path = TEACHER_FILE if current_profile() == "school_teacher" \
        else CLASSBOOK_FILE
    data = load_json_file(path) or {}
    return data.get("system_mode", "ferrum_linux")


# Echo himself knows the school program: on a school profile, the
# school addendum (school/echo_school_addendum.txt) is prepended to
# the messages the brain sees, as a system message. The standard
# profile gets no addendum — its messages go to the brain exactly as
# they arrived. The addendum text is loaded no matter which profile
# booted (1.3.1): a runtime switch into school mode needs it ready.
SCHOOL_ADDENDUM = ""
try:
    with open(os.path.join(SCHOOL_DIR, "echo_school_addendum.txt"),
              encoding="utf-8") as f:
        SCHOOL_ADDENDUM = f.read().strip()
except OSError:
    SCHOOL_ADDENDUM = ""


def brain_messages(messages):
    """The messages the brain actually sees on a chat.

    School profiles: the school addendum first, then a short system
    note with the school's current configured rules, then the
    conversation. Standard profile: the conversation, untouched.
    """
    if current_profile() in SCHOOL_PROFILES and SCHOOL_ADDENDUM:
        return [{"role": "system", "content": SCHOOL_ADDENDUM},
                {"role": "system",
                 "content": school_config_system_note()}] \
            + list(messages)
    return messages


# ---- School governance (the license ceiling) ----------------------------
# Schools program Echo's school behavior under Ferrum's license:
# their own rules live in school/school_rules.json, editable by
# approved tech/admin portal accounts. Founder rules are the ceiling
# — they are NOT keys in any school-editable file, and an attempt to
# set one through the portal is refused by name.
SCHOOL_RULES_FILE = os.path.join(SCHOOL_DIR, "school_rules.json")
FOUNDER_RESERVED_KEYS = ("license_gate", "stop_enabled", "self_rebuild",
                         "ticket_review", "software_removal")


def founder_ceiling_message(key):
    return (f"{key!r} is a founder rule: it stays under Jakob "
            f"Howarth's license and cannot be changed by school "
            f"configuration.")


def load_school_rules():
    """The school's configured rules (defaults when unset)."""
    data = load_json_file(SCHOOL_RULES_FILE) or {}
    return {
        "school_name": data.get("school_name", ""),
        "homework_first": bool(data.get("homework_first", True)),
        "home_limit_default_minutes":
            data.get("home_limit_default_minutes"),
    }


def effective_school_rules():
    """The school's rules as the portal shows them, with the current
    school-hours window (which lives in school_hours.json)."""
    rules = load_school_rules()
    hours = load_school_hours()
    rules["school_hours"] = {
        "days": hours.get("days", []),
        "start": hours.get("start"),
        "end": hours.get("end"),
    }
    return rules


def school_config_system_note():
    """The school's current configured rules, told to the brain on
    school-profile chats — Echo knows them, and follows them within
    Ferrum's license."""
    rules = effective_school_rules()
    limit = rules["home_limit_default_minutes"]
    if limit is None:
        limit = home_use_config()["session_limit_minutes"]
    hours = rules["school_hours"]
    days = ", ".join(hours["days"]) or "(no days set)"
    return (
        "Current school configuration on this machine — the school's "
        "own rules, which you follow within Ferrum's license: "
        f"school name: {rules['school_name'] or '(not set)'}; "
        f"homework-first rule: "
        f"{'on' if rules['homework_first'] else 'off'}; "
        f"home-use session limit: {limit} minutes; "
        f"school portal hours: {days} "
        f"{hours['start']}-{hours['end']}.")


def home_use_config():
    """The Classbook's current home-use rules, read fresh from
    classbook.json (parents/tech rewrite that file through the
    portal, so it must not be cached)."""
    data = load_json_file(CLASSBOOK_FILE) or {}
    cfg = data.get("home_use") or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "session_limit_minutes": cfg.get("session_limit_minutes", 60),
        "homework_check": bool(cfg.get("homework_check", True)),
    }


# ---- Portal accounts ----------------------------------------------------
# Per-person accounts for the school portal, set up by the school's
# tech department their way. Stored as append-only events in
# school/portal_accounts.jsonl, the same pattern as the ticket file:
# account_registered / account_approved / account_denied events, state
# computed on read, the file never rewritten. Passwords are stored
# only as a salted PBKDF2 hash — never plaintext.
ACCOUNT_ROLES = ("tech", "teacher", "student", "parent")
_accounts_lock = threading.Lock()
_tokens = {}
_tokens_lock = threading.Lock()


def _hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt), 100_000).hex()
    return salt, digest


def _password_matches(password, account):
    _, digest = _hash_password(password, account.get("salt", ""))
    return hmac.compare_digest(digest, account.get("password_hash", ""))


def _append_account_event(event):
    with _accounts_lock:
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")


def accounts_state():
    """Replay the account events; return {username: account}.

    An account starts "pending" when registered. Approvals and
    denials are later events; the founder-bootstrap approval also
    marks the account is_admin (the portal admin).
    """
    accounts = {}
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = ev.get("event")
                name = ev.get("username")
                if kind == "account_registered" and name \
                        and name not in accounts:
                    accounts[name] = {
                        "username": name,
                        "role": ev.get("role"),
                        "status": "pending",
                        "is_admin": False,
                        "approval_source": None,
                        "registered_at": ev.get("ts"),
                        "salt": ev.get("salt"),
                        "password_hash": ev.get("password_hash"),
                    }
                elif kind == "account_approved" and name in accounts:
                    accounts[name]["status"] = "approved"
                    accounts[name]["approved_by"] = ev.get("by")
                    if ev.get("source"):
                        accounts[name]["approval_source"] = ev.get("source")
                    if ev.get("admin"):
                        accounts[name]["is_admin"] = True
                elif kind == "account_denied" and name in accounts:
                    accounts[name]["status"] = "denied"
                    accounts[name]["denied_by"] = ev.get("by")
    return accounts


def public_account(account):
    """An account as the portal may show it — never the hash fields."""
    return {k: v for k, v in account.items()
            if k not in ("salt", "password_hash")}


def is_admin_account(account):
    """Admin = the founder-bootstrap admin, or the tech role — once
    the account is approved."""
    return bool(account) and account.get("status") == "approved" \
        and (account.get("is_admin") or account.get("role") == "tech")


def issue_token(username):
    token = uuid.uuid4().hex
    with _tokens_lock:
        _tokens[token] = username
    return token


def account_for_token(username, token):
    """The account behind a login token, or None."""
    if not username or not token:
        return None
    with _tokens_lock:
        owner = _tokens.get(token)
    if owner != username:
        return None
    return accounts_state().get(username)


def recent_log_entries(scan=1000, limit=20):
    """The last `limit` parsed activity-log entries."""
    entries = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-scan:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


# Log events that are about students — what a teacher's inbox shows.
# Proposals and their outcomes, home sessions, and tickets (the school
# runs are student machines; the full firehose stays admin-only).
STUDENT_ACTIVITY_EVENTS = (
    "proposal_received", "proposal_parked", "proposal_refused_never",
    "proposal_auto_executed", "approval_granted", "approval_denied",
    "executed", "home_session_started", "home_session_ended",
    "home_session_limit_reached", "ticket_filed",
)


def student_activity_entries(limit=20):
    out = []
    for entry in recent_log_entries(scan=2000, limit=2000):
        if entry.get("student") \
                or entry.get("profile") == "school_student" \
                or entry.get("event") in STUDENT_ACTIVITY_EVENTS:
            out.append(entry)
    return out[-limit:]


def proposal_decision_refusal(payload, entry):
    """Authorization for /approve and /deny when the caller identifies
    as a portal account. Returns a refusal message, or None if the
    decision may proceed. No username in the payload = the decision is
    made directly (Jakob, as before Phase 2) — unchanged behavior."""
    username = payload.get("username")
    if not username:
        return None
    account = accounts_state().get(username)
    if account is None:
        return f"there is no portal account named {username!r}"
    if account.get("status") != "approved":
        return (f"portal account {username!r} is "
                f"{account.get('status')} — only approved accounts "
                f"decide proposals")
    if is_admin_account(account):
        return None
    if account.get("role") == "teacher":
        if entry.get("approver") == "teacher":
            return None
        return ('teachers may decide only proposals labeled '
                'approver "teacher"')
    return (f"portal account {username!r} (role "
            f"{account.get('role')}) does not decide proposals")


# ---- Classbook home sessions (school_student only) ----------------------
# A student at home gets a timed Echo session. Sessions live in
# memory, like the stopped state; the activity log keeps the record.
HOME_WRAP_UP_LINE = (
    "That's your Echo time for today — time to wrap up. Homework and "
    "school come first, so we're closing here. See you tomorrow."
)
_home_sessions = {}
_home_lock = threading.Lock()


def home_session_for_chat(payload):
    """The home session a /chat call belongs to, with its minutes
    left — or None when no home session applies (any other profile,
    or in-school use with no session started)."""
    if current_profile() != "school_student":
        return None
    with _home_lock:
        sessions = list(_home_sessions.values())
    if not sessions:
        return None
    student = payload.get("student")
    chosen = None
    if student:
        chosen = next((s for s in sessions
                       if s["student"] == student), None)
    if chosen is None:
        chosen = max(sessions, key=lambda s: s["started_monotonic"])
    elapsed = time.monotonic() - chosen["started_monotonic"]
    remaining = chosen["limit_minutes"] * 60 - elapsed
    return {
        "student": chosen["student"],
        "expired": remaining <= 0,
        "minutes_left": max(0, int(math.ceil(remaining / 60))),
    }


def end_home_session(student):
    with _home_lock:
        return _home_sessions.pop(student, None)


# ---- Warning ladder -----------------------------------------------------
# Echo warns users who try what it can't allow, and repeat
# rule-breaking locks them out (Jakob's design, all profiles). A
# violation is a NEVER-tier refusal from /propose — and, in the school
# program, a founder-key override attempt, charged to the attempting
# account. Violations are append-only events in the activity log
# (violation_warning, then user_locked at the threshold); a
# user_unlocked event resets that user's count. Warning 2 is Jakob's
# final-warning line, verbatim.
WARNING_FINAL_LINE = ("I'm sorry, but you're not allowed to use Echo "
                      "anymore if you keep breaking the rules.")
LOCKOUT_LINE = "I'm sorry, but you're not allowed to use Echo anymore."
LOCK_THRESHOLD = 3


def user_key(payload):
    """The violation-tracking key for a request: its "user" field
    when given, else "anonymous"."""
    user = payload.get("user")
    return user if isinstance(user, str) and user.strip() \
        else "anonymous"


def violation_counts():
    """Per-user violation counts, computed from the activity log:
    violation_warning events since the user's last user_unlocked."""
    counts = {}
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                user = ev.get("user")
                if not user:
                    continue
                if ev.get("event") == "violation_warning":
                    counts[user] = counts.get(user, 0) + 1
                elif ev.get("event") == "user_unlocked":
                    counts[user] = 0
    return counts


def locked_users():
    return sorted(u for u, c in violation_counts().items()
                  if c >= LOCK_THRESHOLD)


def is_locked(user):
    return violation_counts().get(user, 0) >= LOCK_THRESHOLD


def record_violation(user, action=None):
    """Log one violation for a user and return their new count. The
    third violation locks the user (logged as user_locked)."""
    count = violation_counts().get(user, 0) + 1
    log_event("violation_warning", user=user, warning=count,
              action=action)
    if count >= LOCK_THRESHOLD:
        log_event("user_locked", user=user, warning=count)
    return count


def warning_message(count, action):
    if count == 1:
        return (f"Warning: Echo never does '{action}'. This is a "
                f"warning — the refusal is logged.")
    if count == 2:
        return WARNING_FINAL_LINE
    return LOCKOUT_LINE


# ---- HTTP handler -------------------------------------------------------
class EchoHandler(BaseHTTPRequestHandler):
    server_version = "EchoLinux/1.3.1"

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _stopped_refusal(self, endpoint):
        log_event("refused_while_stopped", endpoint=endpoint)
        self._send_json(409, {
            "ok": False,
            "error": "Echo is stopped. STOP wins over everything — "
                     "Echo will not work again until a /start arrives.",
        })

    def _license_refusal(self, endpoint):
        log_event("refused_license", endpoint=endpoint)
        self._send_json(403, {
            "ok": False,
            "error": LICENSE_LINE,
            "message": LICENSE_LINE,
        })

    def _locked_refusal(self, endpoint, user):
        log_event("refused_locked", endpoint=endpoint, user=user)
        self._send_json(403, {
            "ok": False, "state": "locked",
            "error": LOCKOUT_LINE, "message": LOCKOUT_LINE,
        })

    def _never_refusal(self, payload, action, rule, **log_fields):
        """A NEVER-tier refusal from /propose, run through the
        warning ladder: the refusal is a violation for the asking
        user, the response carries their warning, and the third
        violation locks them on the spot."""
        user = user_key(payload)
        log_event("proposal_refused_never", action=action, rule=rule,
                  user=user, **log_fields)
        count = record_violation(user, action=action)
        if count >= LOCK_THRESHOLD:
            self._send_json(403, {
                "ok": False, "state": "locked", "action": action,
                "error": LOCKOUT_LINE, "message": LOCKOUT_LINE,
                "warning": count, "warning_message": LOCKOUT_LINE,
            })
            return
        self._send_json(403, {
            "ok": False, "state": "refused_never", "action": action,
            "rule": rule, "warning": count,
            "warning_message": warning_message(count, action),
        })

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        def q(name):
            values = query.get(name)
            return values[0] if values else None

        if path == "/status":
            log_event("status", state="stopped" if is_stopped() else "running")
            self._send_json(200, status_payload())
        elif path == "/mode":
            # Switchable modes (1.3.1): which mode Echo is in right
            # now. Reading it changes nothing, like /status.
            log_event("mode_status", mode=current_mode(),
                      profile=current_profile(),
                      beta_mode_lock=beta_mode_lock())
            self._send_json(200, {
                "ok": True,
                "mode": current_mode(),
                "profile": current_profile(),
                "modes": ["normal", "school"],
                "beta_mode_lock": beta_mode_lock(),
            })
        elif path == "/models":
            # The model registry (v1.3.0): the whole roster with
            # statuses and tiers, plus the backends and which one
            # is active. Read-only, like the policies index —
            # reading it changes nothing and starts nothing.
            body = models_payload()
            log_event("models_listed", count=len(MODEL_LIST),
                      live=body["summary"]["live_count"],
                      active_backend=ACTIVE_BACKEND_ID)
            self._send_json(200, body)
        elif path == "/policies":
            # The baked-in agreements index: names, version, effective
            # date. Customer-facing and read-only — no gate.
            log_event("policies_index", count=len(POLICY_DOC_LIST))
            self._send_json(200, {
                "ok": True,
                "version": POLICIES_META.get("version"),
                "effective_date": POLICIES_META.get("effective_date"),
                "status": POLICIES_META.get("status"),
                "applies_to": POLICIES_META.get("applies_to"),
                "documents": [{"slug": d["slug"], "name": d["name"]}
                              for d in POLICY_DOC_LIST],
            })
        elif path.startswith("/policies/"):
            slug = path[len("/policies/"):].strip("/").lower()
            doc = POLICIES.get(slug)
            if doc is None:
                log_event("policy_not_found", slug=slug)
                self._send_json(404, {
                    "ok": False,
                    "error": f"No policy document named '{slug}'.",
                    "documents": [d["slug"] for d in POLICY_DOC_LIST],
                })
            else:
                log_event("policy_served", slug=slug)
                self._send_json(200, {
                    "ok": True, "slug": slug, "name": doc["name"],
                    "version": POLICIES_META.get("version"),
                    "effective_date":
                        POLICIES_META.get("effective_date"),
                    "text": doc["text"],
                })
        elif path == "/license":
            data = load_json_file(LICENSE_FILE) or {}
            accepted = bool(data.get("accepted"))
            log_event("license_status", accepted=accepted)
            self._send_json(200, {
                "ok": True, "accepted": accepted,
                "by": data.get("by") if accepted else None,
                "ts": data.get("ts") if accepted else None,
                "summary": LICENSE_SUMMARY,
            })
        elif path == "/pending":
            items = pending_list()
            log_event("pending_listed", count=len(items))
            self._send_json(200, {"ok": True, "pending": items})
        elif path == "/tickets":
            # Reading the ticket queue executes nothing, so it stays
            # available while stopped — like /pending.
            items = tickets_with_status()
            log_event("tickets_listed", count=len(items),
                      open=sum(1 for t in items if t["status"] == "open"))
            self._send_json(200, {"ok": True, "tickets": items})
        elif path == "/plugins":
            # The platform plugin pack (Jakob, 2026-10-19): one
            # plugin per platform — YouTube, Facebook, Instagram, X,
            # TikTok — each the sanctioned, official-API route to its
            # platform, with Jakob's rules enforced in the plugins'
            # shared base. Reading the list changes nothing and
            # connects nothing: every plugin reports "not_connected"
            # until Jakob hooks up that account himself. Plugin
            # *actions* live in the plugins package and log rich,
            # watchable entries for every attempt.
            from plugins import plugins_payload
            payload = plugins_payload(log=log_event)
            log_event("plugins_listed",
                      count=len(payload["plugins"]),
                      connected=sum(1 for p in payload["plugins"]
                                    if p["status"] == "connected"))
            self._send_json(200, payload)
        elif path == "/portal_status":
            # The school portal's status: which profile this machine
            # runs, its chosen system setup, the school's hours, and
            # whether Echo is on or off. Reading it changes nothing.
            hours = load_school_hours()
            inside = in_school_hours()
            log_event("portal_status", profile=current_profile(),
                      in_school_hours=inside)
            self._send_json(200, {
                "ok": True,
                "profile": current_profile(),
                "mode": current_mode(),
                "system_mode": current_system_mode(),
                "school_hours": {
                    "days": hours.get("days", []),
                    "start": hours.get("start"),
                    "end": hours.get("end"),
                },
                "in_school_hours": inside,
                "portal_state": "stopped" if is_stopped() else "running",
                "state": "stopped" if is_stopped() else "running",
            })
        elif path == "/portal_school_rules":
            # The school's configured rules, readable by the same
            # tech/admin accounts that may set them.
            username = q("username")
            account = account_for_token(username, q("token"))
            if account is None or not is_admin_account(account):
                log_event("portal_school_rules_refused",
                          username=username, reason="not_admin")
                self._send_json(403, {"ok": False, "error":
                    "school rules are set by approved tech/admin "
                    "portal accounts"})
                return
            log_event("portal_school_rules_read", username=username)
            self._send_json(200, {"ok": True,
                                  "school_rules": effective_school_rules()})
        elif path == "/portal_echo_view":
            # Tech-department oversight: Echo's live status plus the
            # recent activity log. Jakob's two-layer rule: the status
            # is for everyone; the full log is owner/admin-level —
            # here, approved tech/admin accounts only. Read-only
            # observation: it never interrupts Echo or anyone's work.
            username = q("username")
            account = account_for_token(username, q("token"))
            if account is None or not is_admin_account(account):
                log_event("portal_echo_view_refused", username=username)
                self._send_json(403, {"ok": False, "error":
                    "the oversight view (status plus the full activity "
                    "log) is for approved tech/admin portal accounts"})
                return
            entries = recent_log_entries(limit=20)
            log_event("portal_echo_view", username=username,
                      entries=len(entries))
            self._send_json(200, {
                "ok": True, "username": username,
                "status": status_payload(),
                "recent_log": entries,
            })
        elif path == "/teacher_inbox":
            # The teacher portal: their approvals inbox plus eyes on
            # their classroom — recent student activity, NOT the full
            # admin log. Teachers only; tech/admin have their own
            # oversight view, students and parents have neither.
            username = q("username")
            account = account_for_token(username, q("token"))
            if account is None \
                    or account.get("status") != "approved" \
                    or account.get("role") != "teacher":
                log_event("teacher_inbox_refused", username=username)
                self._send_json(403, {"ok": False, "error":
                    "the teacher inbox is for approved teacher portal "
                    "accounts — tech/admin use the portal oversight "
                    "view instead"})
                return
            inbox = [p for p in pending_list()
                     if p.get("approver") == "teacher"]
            activity = student_activity_entries(limit=20)
            log_event("teacher_inbox_viewed", username=username,
                      pending=len(inbox), activity=len(activity))
            self._send_json(200, {
                "ok": True, "username": username,
                "pending_approvals": inbox,
                "student_activity": activity,
            })
        else:
            log_event("unknown_route", method="GET", path=path)
            self._send_json(404, {"ok": False, "error": "unknown route"})

    def do_POST(self):
        try:
            payload = self._read_json()
        except Exception as e:
            log_event("bad_request", path=self.path, error=str(e))
            self._send_json(400, {"ok": False, "error": f"bad JSON body: {e}"})
            return

        if self.path == "/stop":
            # STOP is always allowed — it is the one call that must never
            # be refused, even by the stopped state itself.
            set_stopped(True)
            log_event("stop")
            self._send_json(200, {"ok": True, "state": "stopped"})

        elif self.path == "/start":
            set_stopped(False)
            log_event("start")
            self._send_json(200, {"ok": True, "state": "running"})

        elif self.path == "/mode":
            # Switchable modes (1.3.1, Jakob's order): flip Echo
            # between normal mode (standard profile) and school mode
            # (school_student profile). An owner control like /start
            # — it works while stopped, and the choice is saved to
            # mode_state.json so it survives restarts.
            # Beta mode lock (1.3.2, Jakob's order): while the lock
            # is on, the beta version must stay in normal mode, so a
            # flip to school is refused (403). The lock itself is
            # applied or lifted here with {"beta_lock": true|false}.
            handled = False
            if "beta_lock" in payload:
                want = payload.get("beta_lock")
                if not isinstance(want, bool):
                    self._send_json(400, {"ok": False, "error":
                        "beta_lock must be true or false"})
                    return
                set_beta_lock(want, "api")
                handled = True
            if "mode" in payload:
                outcome = set_mode(payload.get("mode"), "api")
                if outcome is None:
                    self._send_json(400, {"ok": False, "error":
                        "mode must be \"school\" or \"normal\""})
                    return
                if outcome[0] == "locked":
                    self._send_json(403, {"ok": False, "error":
                        "Normal mode is required on the beta "
                        "version — the beta mode lock is on, so "
                        "Echo cannot switch to school mode.",
                        "mode": current_mode(),
                        "beta_mode_lock": True})
                    return
                handled = True
            if not handled:
                self._send_json(400, {"ok": False, "error":
                    "give \"mode\": \"school\" or \"normal\", or "
                    "\"beta_lock\": true or false"})
                return
            self._send_json(200, {"ok": True, "mode": current_mode(),
                                  "profile": current_profile(),
                                  "beta_mode_lock": beta_mode_lock()})

        elif self.path == "/kill":
            # THE KILL SWITCH (Jakob, 2026-10-18): beyond STOP. STOP
            # parks Echo and Start undoes it from inside the software.
            # The kill switch shuts Echo's server ALL the way down:
            # no chat, no panel, no Start button can reach him,
            # because nothing is listening. Only the owner starting
            # Echo's server again on the machine brings him back.
            set_stopped(True)
            log_event("kill_switch")
            self._send_json(200, {"ok": True, "state": "killed",
                "message": "Echo is fully shut down — the kill switch "
                           "was engaged. He is not paused; his server "
                           "is off. Only the owner starting Echo's "
                           "server again brings him back."})
            threading.Timer(0.6, os._exit, args=(0,)).start()

        elif self.path == "/license_accept":
            # The boot license gate: a person on this machine agrees
            # to Ferrum's license before use. The acceptance is
            # recorded in license_state.json and logged. In the school
            # profiles, the accepting "by" is an approved admin/tech
            # portal account — that is the machine's acceptance; this
            # prototype records the name as given.
            by = payload.get("by")
            if not isinstance(by, str) or not by.strip():
                self._send_json(400, {"ok": False, "error":
                    "accepting the license needs a name in \"by\""})
                return
            by = by.strip()
            ts = datetime.now(timezone.utc).isoformat()
            with open(LICENSE_FILE, "w", encoding="utf-8") as f:
                json.dump({"accepted": True, "by": by, "ts": ts}, f,
                          indent=2)
                f.write("\n")
            log_event("license_accepted", by=by)
            self._send_json(200, {"ok": True, "accepted": True,
                                  "by": by, "ts": ts})

        elif self.path == "/unlock":
            # Owner action: clear a user's warning-ladder lock. In
            # the school profiles this belongs to admin/tech portal
            # accounts; under the standard profile it is a plain
            # owner action, like /start.
            target = payload.get("user")
            if not isinstance(target, str) or not target.strip():
                self._send_json(400, {"ok": False, "error":
                    "unlock needs the locked user's name in \"user\""})
                return
            target = target.strip()
            by = "owner"
            if current_profile() in SCHOOL_PROFILES:
                account = account_for_token(payload.get("username"),
                                            payload.get("token"))
                if account is None or not is_admin_account(account):
                    log_event("unlock_refused", user=target,
                              by=payload.get("username"))
                    self._send_json(403, {"ok": False, "error":
                        "unlocking a user is for admin/tech portal "
                        "accounts"})
                    return
                by = payload.get("username")
            was_locked = is_locked(target)
            log_event("user_unlocked", user=target, by=by,
                      was_locked=was_locked)
            self._send_json(200, {"ok": True, "user": target,
                                  "state": "unlocked",
                                  "was_locked": was_locked, "by": by})

        elif self.path == "/chat":
            if not license_accepted():
                self._license_refusal("/chat")
                return
            if is_locked(user_key(payload)):
                self._locked_refusal("/chat", user_key(payload))
                return
            if is_stopped():
                self._stopped_refusal("/chat")
                return
            messages = payload.get("messages", [])
            log_event("chat", messages=len(messages))
            # Ticket rule: a self-change ask in the latest user message
            # files a ticket automatically, before the brain answers.
            # The brain still replies normally — the system prompt's
            # ticket rule makes Echo decline and explain the ticket.
            # App-request rule (2026-10-19): an ask to obtain/install
            # a new app on Echo's Linux machine files an app_request
            # ticket the same way; the prompt's app-request rule makes
            # Echo explain the ticket and install nothing.
            filed_id = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str) \
                            and detect_self_change(content):
                        filed_id = file_ticket("self_change", content, "chat")
                    elif isinstance(content, str) \
                            and detect_app_request(content):
                        filed_id = file_ticket(
                            "app_request",
                            app_request_ticket_text(content), "chat")
                    break
            # Classbook home use: a home session past its limit ends
            # the conversation with Echo's wrap-up line. In-school
            # use (no home session) is untouched by this.
            home = home_session_for_chat(payload)
            if home is not None and home["expired"]:
                end_home_session(home["student"])
                log_event("home_session_limit_reached",
                          student=home["student"])
                self._send_json(403, {
                    "ok": False, "state": "home_session_limit_reached",
                    "error": HOME_WRAP_UP_LINE,
                    "message": HOME_WRAP_UP_LINE,
                    "student": home["student"],
                })
                return
            # Switchable modes (1.3.1): a plain ask in chat — "switch
            # to normal mode", "school mode" — flips Echo between
            # his normal and school modes right here, answered
            # directly like the baked-in agreements below (no brain
            # call). The choice is saved and survives restarts.
            mode_ask = None
            if not filed_id:
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        content = msg.get("content")
                        if isinstance(content, str):
                            mode_ask = detect_mode_switch(content)
                        break
            if mode_ask is not None:
                outcome = set_mode(mode_ask, "chat")
                if outcome[0] == "locked":
                    # Beta mode lock (1.3.2): a plain refusal, right
                    # here — no flip, no brain call.
                    line = ("I have to stay in normal mode on the "
                            "beta version.")
                    result = {"ok": True, "reply": line,
                              "mode": current_mode(),
                              "profile": current_profile(),
                              "beta_mode_lock": True}
                else:
                    profile, changed = outcome
                    if not changed:
                        line = f"I'm already in {mode_ask} mode."
                    elif mode_ask == "school":
                        line = ("Done — I'm in school mode now: the "
                                "Classbook student rules apply.")
                    else:
                        line = "Done — I'm in normal mode now."
                    result = {"ok": True, "reply": line,
                              "mode": mode_ask, "profile": profile}
                log_event("chat_reply", ok=True)
                self._send_json(200, result)
                return
            # Baked-in agreements: a direct ask for one of the Ferrum
            # Software Policies is answered with the document itself —
            # the texts ship in the software (GET /policies), so no
            # brain call is needed. A self-change ask above still
            # goes to the brain exactly as before (its ticket is
            # already filed; the brain's reply carries the decline).
            # Model routing (v1.3.0): an optional "model" in the
            # payload — or a plain ask in the message itself — is
            # resolved against the registry before the brain runs. A
            # model that is not live yet is answered honestly here;
            # Echo never pretends an unreleased model is running.
            chosen_model = None
            model_result = None
            if not filed_id:
                outcome = model_route(payload, messages)
                if outcome[0] == "error":
                    log_event("chat_unknown_model", model=outcome[1])
                    self._send_json(400, {
                        "ok": False,
                        "error": f"Echo has no model named "
                                 f"{outcome[1]!r}.",
                        "models": [m["id"] for m in MODEL_LIST],
                    })
                    return
                if outcome[0] == "reply":
                    model_result = outcome[1]
                elif outcome[0] == "chosen":
                    chosen_model = outcome[1]
            policy_slug = None
            if not filed_id and model_result is None:
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        content = msg.get("content")
                        if isinstance(content, str):
                            policy_slug = detect_policy_request(content)
                        break
            if model_result is not None:
                result = model_result
            elif policy_slug:
                log_event("chat_policy_reply", slug=policy_slug)
                result = {"ok": True,
                          "reply": POLICIES[policy_slug]["text"],
                          "policy_document": policy_slug}
            else:
                try:
                    result = ask_brain(brain_messages(messages))
                except Exception as e:
                    result = {"ok": False,
                              "error": f"brain call failed: {e}"}
                if chosen_model is not None and result.get("ok"):
                    result["model"] = chosen_model["id"]
                    result["model_status"] = chosen_model["status"]
            if filed_id:
                result["ticket_filed"] = filed_id
            if home is not None:
                result["home_session"] = {
                    "student": home["student"],
                    "minutes_left": home["minutes_left"],
                }
            log_event("chat_reply", ok=result.get("ok", False))
            self._send_json(200 if result.get("ok") else 502, result)

        elif self.path == "/lookup":
            if is_stopped():
                self._stopped_refusal("/lookup")
                return
            url = payload.get("url", "")
            log_event("lookup", url=url)
            result = browser_tool.fetch_page(url)
            log_event("lookup_result", url=url, ok=result.get("ok", False))
            self._send_json(200 if result.get("ok") else 400, result)

        elif self.path == "/propose":
            if not license_accepted():
                self._license_refusal("/propose")
                return
            if is_locked(user_key(payload)):
                self._locked_refusal("/propose", user_key(payload))
                return
            if is_stopped():
                self._stopped_refusal("/propose")
                return
            action = payload.get("action")
            detail = payload.get("detail")
            if not isinstance(detail, dict):
                detail = {}
            log_event("proposal_received", action=action)
            if action not in KNOWN_ACTIONS:
                self._never_refusal(payload, action, UNKNOWN_ACTION_RULE)
                return
            if current_profile() == "school_student" \
                    and action == "remember":
                # The stricter student rule: on a Classbook, Echo
                # remembering personal notes is not ASK FIRST — it is
                # NEVER, and the refusal names the rule.
                self._never_refusal(payload, action,
                                    STUDENT_REMEMBER_RULE)
                return
            if action in ("lookup", "save_lookup"):
                reason = never_url_reason(detail.get("url", ""))
                if reason:
                    self._never_refusal(payload, action, reason,
                                        url=detail.get("url", ""))
                    return
            if action == "remember":
                note = detail.get("note")
                if not isinstance(note, str) or not note.strip():
                    log_event("bad_request", path=self.path,
                              error="remember needs a non-empty note")
                    self._send_json(400, {"ok": False, "error":
                        "remember proposals need detail.note (non-empty text)"})
                    return
            if action == "lookup":
                # AUTO tier: run it now, exactly like /lookup.
                result = browser_tool.fetch_page(detail.get("url", ""))
                log_event("proposal_auto_executed", action=action,
                          url=detail.get("url", ""),
                          ok=result.get("ok", False))
                self._send_json(200 if result.get("ok") else 400,
                                {"ok": result.get("ok", False),
                                 "state": "executed", "action": action,
                                 "result": result})
                return
            # ASK FIRST tier: park it. Nothing executes until /approve.
            pid = uuid.uuid4().hex[:8]
            entry = {
                "id": pid,
                "action": action,
                "detail": detail,
                "summary": proposal_summary(action, detail),
                "proposed_at": datetime.now(timezone.utc).isoformat(),
            }
            if current_profile() in SCHOOL_PROFILES:
                # In the school program, parked proposals wait for a
                # teacher's approval — the label says so.
                entry["approver"] = "teacher"
            with _pending_lock:
                _pending[pid] = entry
            log_event("proposal_parked", id=pid, action=action,
                      summary=entry["summary"])
            response = {"ok": True, "state": "awaiting_approval",
                        "id": pid, "action": action,
                        "summary": entry["summary"]}
            if "approver" in entry:
                response["approver"] = entry["approver"]
            self._send_json(200, response)

        elif self.path == "/approve":
            if not license_accepted():
                self._license_refusal("/approve")
                return
            if is_stopped():
                self._stopped_refusal("/approve")
                return
            pid = payload.get("id")
            with _pending_lock:
                entry = _pending.get(pid)
            if entry is None:
                log_event("approval_unknown_id", id=pid)
                self._send_json(404, {"ok": False,
                                      "error": "no pending proposal with that id"})
                return
            refusal = proposal_decision_refusal(payload, entry)
            if refusal:
                log_event("approval_refused", id=pid,
                          by=payload.get("username"), reason=refusal)
                self._send_json(403, {"ok": False, "error": refusal})
                return
            with _pending_lock:
                entry = _pending.pop(pid, None)
            if entry is None:  # decided by someone else in between
                self._send_json(404, {"ok": False,
                                      "error": "no pending proposal with that id"})
                return
            grant = {"id": pid, "action": entry["action"]}
            if payload.get("username"):
                grant["by"] = payload["username"]
            log_event("approval_granted", **grant)
            try:
                result = execute_proposal(entry)
            except Exception as e:
                result = {"ok": False, "action": entry["action"],
                          "error": f"execution failed: {e}"}
            log_event("executed", id=pid, action=entry["action"],
                      ok=result.get("ok", False))
            self._send_json(200 if result.get("ok") else 400,
                            {"ok": result.get("ok", False),
                             "state": "executed", "id": pid,
                             "action": entry["action"], "result": result})

        elif self.path == "/deny":
            if not license_accepted():
                self._license_refusal("/deny")
                return
            # Deny only discards — it executes nothing, so it stays
            # available while stopped (a parked item can be thrown away
            # even when Echo is frozen).
            pid = payload.get("id")
            with _pending_lock:
                entry = _pending.get(pid)
            if entry is None:
                log_event("denial_unknown_id", id=pid)
                self._send_json(404, {"ok": False,
                                      "error": "no pending proposal with that id"})
                return
            refusal = proposal_decision_refusal(payload, entry)
            if refusal:
                log_event("denial_refused", id=pid,
                          by=payload.get("username"), reason=refusal)
                self._send_json(403, {"ok": False, "error": refusal})
                return
            with _pending_lock:
                entry = _pending.pop(pid, None)
            if entry is None:  # decided by someone else in between
                self._send_json(404, {"ok": False,
                                      "error": "no pending proposal with that id"})
                return
            denied = {"id": pid, "action": entry["action"]}
            if payload.get("username"):
                denied["by"] = payload["username"]
            log_event("approval_denied", **denied)
            self._send_json(200, {"ok": True, "state": "denied", "id": pid,
                                  "action": entry["action"]})

        elif self.path == "/ticket":
            if not license_accepted():
                self._license_refusal("/ticket")
                return
            if is_locked(user_key(payload)):
                self._locked_refusal("/ticket", user_key(payload))
                return
            if is_stopped():
                self._stopped_refusal("/ticket")
                return
            kind = payload.get("kind")
            text = payload.get("text")
            source = payload.get("source") or "api"
            if kind not in TICKET_KINDS:
                log_event("bad_request", path=self.path,
                          error=f"invalid ticket kind: {kind!r}")
                self._send_json(400, {"ok": False, "error":
                    "ticket kind must be one of: "
                    + ", ".join(TICKET_KINDS)})
                return
            if not isinstance(text, str) or not text.strip():
                log_event("bad_request", path=self.path,
                          error="ticket filed without text")
                self._send_json(400, {"ok": False, "error":
                    "a ticket needs a non-empty text"})
                return
            tid = file_ticket(kind, text.strip(), source)
            self._send_json(200, {"ok": True, "id": tid,
                                  "state": "awaiting_review"})

        elif self.path == "/ticket_review":
            if is_stopped():
                self._stopped_refusal("/ticket_review")
                return
            tid = payload.get("id")
            decision = payload.get("decision")
            if decision not in ("approved", "denied"):
                log_event("bad_request", path=self.path,
                          error=f"invalid ticket decision: {decision!r}")
                self._send_json(400, {"ok": False, "error":
                    "decision must be \"approved\" or \"denied\""})
                return
            ticket = next((t for t in tickets_with_status()
                           if t["id"] == tid), None)
            if ticket is None:
                log_event("ticket_review_unknown_id", id=tid)
                self._send_json(404, {"ok": False,
                                      "error": "no ticket with that id"})
                return
            if ticket["status"] != "open":
                log_event("ticket_review_conflict", id=tid,
                          status=ticket["status"])
                self._send_json(409, {"ok": False, "error":
                    f"ticket {tid} was already reviewed "
                    f"({ticket['status']}) — a ticket is decided once, "
                    f"by Jakob"})
                return
            _append_ticket_event({
                "event": "ticket_reviewed", "id": tid,
                "ts": datetime.now(timezone.utc).isoformat(),
                "decision": decision,
            })
            log_event("ticket_reviewed", id=tid, decision=decision)
            self._send_json(200, {"ok": True, "id": tid,
                                  "state": decision})

        elif self.path == "/portal_register":
            # Portal accounts are set up by the school's tech
            # department, their way. Every account starts pending;
            # approval comes from the founder bootstrap (the first
            # login) or from an approved admin.
            username = payload.get("username")
            password = payload.get("password")
            role = payload.get("role")
            if not isinstance(username, str) or not username.strip() \
                    or not isinstance(password, str) or not password \
                    or role not in ACCOUNT_ROLES:
                log_event("bad_request", path=self.path,
                          error="portal register needs username, "
                                "password, and a valid role")
                self._send_json(400, {"ok": False, "error":
                    "registering needs a username, a password, and a "
                    "role of " + ", ".join(ACCOUNT_ROLES)})
                return
            username = username.strip()
            if username in accounts_state():
                log_event("portal_register_conflict", username=username)
                self._send_json(409, {"ok": False, "error":
                    f"a portal account named {username!r} already exists"})
                return
            salt, digest = _hash_password(password)
            _append_account_event({
                "event": "account_registered",
                "ts": datetime.now(timezone.utc).isoformat(),
                "username": username, "role": role,
                "salt": salt, "password_hash": digest,
                "status": "pending",
            })
            log_event("portal_account_registered", username=username,
                      role=role)
            self._send_json(200, {"ok": True, "username": username,
                                  "role": role, "status": "pending"})

        elif self.path == "/portal_login":
            username = payload.get("username")
            password = payload.get("password")
            account = accounts_state().get(username) \
                if isinstance(username, str) else None
            if account is None or not isinstance(password, str) \
                    or not _password_matches(password, account):
                log_event("portal_login_failed", username=username)
                self._send_json(401, {"ok": False, "error":
                    "unknown username or wrong password"})
                return
            if account["status"] == "denied":
                log_event("portal_login_denied_account",
                          username=username)
                self._send_json(403, {"ok": False, "error":
                    "this portal account was denied — it cannot log in"})
                return
            # Jakob's founder bootstrap rule: the FIRST person to log
            # into a school's portal automatically gets his approval —
            # that first successful login auto-approves the account as
            # the portal admin.
            bootstrapped = False
            if not any(a.get("is_admin")
                       for a in accounts_state().values()):
                _append_account_event({
                    "event": "account_approved",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "username": username, "by": FOUNDER_RULE_SOURCE,
                    "source": FOUNDER_RULE_SOURCE, "admin": True,
                })
                log_event("portal_first_login_auto_approved",
                          username=username,
                          approval_source=FOUNDER_RULE_SOURCE)
                account = accounts_state()[username]
                bootstrapped = True
            token = issue_token(username)
            log_event("portal_login", username=username,
                      role=account["role"], status=account["status"],
                      bootstrapped=bootstrapped)
            self._send_json(200, {
                "ok": True, "username": username,
                "role": account["role"], "status": account["status"],
                "is_admin": is_admin_account(account),
                "bootstrapped_admin": bootstrapped,
                "token": token,
            })

        elif self.path == "/portal_enter":
            # Portal entry keys off accounts and their roles.
            # Teachers and admins may enter at any time; students may
            # not enter during school hours — and that refusal is in
            # Echo's own words (Jakob's wording).
            username = payload.get("username")
            account = account_for_token(username, payload.get("token"))
            inside = in_school_hours()
            if account is None:
                if payload.get("role") == "student" and inside:
                    log_event("portal_entry_refused", username=username,
                              reason="school_hours")
                    self._send_json(403, {"ok": False,
                                          "error": STUDENT_PORTAL_REFUSAL,
                                          "message": STUDENT_PORTAL_REFUSAL})
                    return
                log_event("portal_entry_refused", username=username,
                          reason="no_account")
                self._send_json(403, {"ok": False, "error":
                    "portal entry needs a logged-in, approved portal "
                    "account"})
                return
            if account["status"] != "approved":
                if account["status"] == "pending":
                    msg = ("your portal account is pending — it cannot "
                           "enter the portal until an admin approves it")
                else:
                    msg = ("your portal account was denied — it cannot "
                           "enter the portal")
                log_event("portal_entry_refused", username=username,
                          reason=f"account_{account['status']}")
                self._send_json(403, {"ok": False, "error": msg})
                return
            if account["role"] == "student" and inside:
                log_event("portal_entry_refused", username=username,
                          reason="school_hours")
                self._send_json(403, {"ok": False,
                                      "error": STUDENT_PORTAL_REFUSAL,
                                      "message": STUDENT_PORTAL_REFUSAL})
                return
            log_event("portal_entered", username=username,
                      role=account["role"], in_school_hours=inside)
            self._send_json(200, {"ok": True, "entered": True,
                                  "username": username,
                                  "role": account["role"],
                                  "in_school_hours": inside})

        elif self.path == "/portal_power":
            # The portal is the control place: authorized people turn
            # Echo off and on here, and it is the REAL stop/start — an
            # off Echo refuses work with the same 409 STOP behavior as
            # /stop. This route is never stopped out itself (it is how
            # Echo gets turned back on), and students/parents never
            # hold the power controls, in school hours or out.
            if not license_accepted():
                self._license_refusal("/portal_power")
                return
            username = payload.get("username")
            action = payload.get("action")
            if action not in ("off", "on"):
                self._send_json(400, {"ok": False, "error":
                    "portal power action must be \"off\" or \"on\""})
                return
            account = account_for_token(username, payload.get("token"))
            if account is None or account["status"] != "approved" \
                    or not (account["role"] == "teacher"
                            or is_admin_account(account)):
                log_event("portal_power_refused", username=username,
                          action=action)
                self._send_json(403, {"ok": False, "error":
                    "only approved teacher or tech/admin portal "
                    "accounts control Echo's power"})
                return
            set_stopped(action == "off")
            log_event("portal_power", username=username, action=action,
                      state="stopped" if action == "off" else "running")
            self._send_json(200, {"ok": True, "action": action,
                                  "state": "stopped" if action == "off"
                                  else "running"})

        elif self.path in ("/portal_approve", "/portal_deny"):
            # An approved admin decides a pending account: "by" names
            # the admin account, and it must be an approved admin.
            approve = self.path == "/portal_approve"
            username = payload.get("username")
            by = payload.get("by")
            state = accounts_state()
            decider = state.get(by) if isinstance(by, str) else None
            if decider is None or not is_admin_account(decider):
                log_event("portal_account_decision_refused",
                          username=username, by=by,
                          decision="approved" if approve else "denied")
                self._send_json(403, {"ok": False, "error":
                    "only an approved admin portal account can approve "
                    "or deny accounts"})
                return
            target = state.get(username) \
                if isinstance(username, str) else None
            if target is None:
                self._send_json(404, {"ok": False, "error":
                    "no portal account with that username"})
                return
            if target["status"] != "pending":
                self._send_json(409, {"ok": False, "error":
                    f"account {username!r} is already "
                    f"{target['status']} — only pending accounts are "
                    f"decided"})
                return
            _append_account_event({
                "event": "account_approved" if approve
                         else "account_denied",
                "ts": datetime.now(timezone.utc).isoformat(),
                "username": username, "by": by,
            })
            log_event("portal_account_approved" if approve
                      else "portal_account_denied",
                      username=username, by=by)
            self._send_json(200, {"ok": True, "username": username,
                                  "status": "approved" if approve
                                  else "denied", "by": by})

        elif self.path == "/portal_school_rules":
            # Governance: the school's own rules for its machines,
            # set by approved tech/admin portal accounts; Echo agrees
            # to and follows them within Ferrum's license. Founder
            # rules are the ceiling — they are not keys in any
            # school-editable file, and trying to set one is refused
            # by name and logged.
            username = payload.get("username")
            account = account_for_token(username, payload.get("token"))
            if account is None or not is_admin_account(account):
                log_event("portal_school_rules_refused",
                          username=username, reason="not_admin")
                self._send_json(403, {"ok": False, "error":
                    "school rules are set by approved tech/admin "
                    "portal accounts"})
                return
            for key in payload:
                if key in FOUNDER_RESERVED_KEYS:
                    msg = founder_ceiling_message(key)
                    count = record_violation(
                        username, action=f"school_rules:{key}")
                    log_event("portal_school_rules_refused_founder_key",
                              username=username, key=key, warning=count)
                    self._send_json(400, {"ok": False, "error": msg,
                                          "rule": msg, "warning": count,
                                          "warning_message":
                                              warning_message(count,
                                                              key)})
                    return
            rules_now = load_school_rules()
            data = load_json_file(SCHOOL_RULES_FILE) or {}
            changes = {}
            if "school_name" in payload:
                value = payload["school_name"]
                if not isinstance(value, str) or len(value) > 120:
                    self._send_json(400, {"ok": False, "error":
                        "school_name must be a short text label"})
                    return
                changes["school_name"] = {
                    "from": rules_now["school_name"], "to": value}
                data["school_name"] = value
            if "homework_first" in payload:
                value = payload["homework_first"]
                if not isinstance(value, bool):
                    self._send_json(400, {"ok": False, "error":
                        "homework_first must be true or false"})
                    return
                changes["homework_first"] = {
                    "from": rules_now["homework_first"], "to": value}
                data["homework_first"] = value
            if "home_limit_default_minutes" in payload:
                value = payload["home_limit_default_minutes"]
                if value is not None \
                        and (not isinstance(value, int)
                             or isinstance(value, bool)
                             or value < 0 or value > 600):
                    self._send_json(400, {"ok": False, "error":
                        "home_limit_default_minutes must be a whole "
                        "number from 0 to 600, or null"})
                    return
                changes["home_limit_default_minutes"] = {
                    "from": rules_now["home_limit_default_minutes"],
                    "to": value}
                data["home_limit_default_minutes"] = value
            hours_change = None
            if "school_hours" in payload:
                window = payload["school_hours"]
                if not isinstance(window, dict):
                    self._send_json(400, {"ok": False, "error":
                        "school_hours must be an object with days, "
                        "start, end"})
                    return
                hours = dict(load_school_hours())
                valid_days = ("mon", "tue", "wed", "thu", "fri",
                              "sat", "sun")
                if "days" in window:
                    days = window["days"]
                    if not isinstance(days, list) or any(
                            str(d).strip().lower()[:3] not in valid_days
                            for d in days):
                        self._send_json(400, {"ok": False, "error":
                            "school_hours.days must be a list of day "
                            "names (mon, tue, ...)"})
                        return
                    hours["days"] = [str(d).strip().lower()[:3]
                                     for d in days]
                for field in ("start", "end"):
                    if field in window:
                        try:
                            datetime.strptime(str(window[field]),
                                              "%H:%M")
                        except ValueError:
                            self._send_json(400, {"ok": False, "error":
                                f"school_hours.{field} must be HH:MM"})
                            return
                        hours[field] = str(window[field])
                with open(SCHOOL_HOURS_FILE, "w",
                          encoding="utf-8") as f:
                    json.dump(hours, f, indent=2, sort_keys=True)
                    f.write("\n")
                hours_change = {"days": hours.get("days"),
                                "start": hours.get("start"),
                                "end": hours.get("end")}
            if not changes and hours_change is None:
                self._send_json(400, {"ok": False, "error":
                    "nothing to change — the school can set "
                    "school_name, homework_first, "
                    "home_limit_default_minutes, and school_hours"})
                return
            if changes:
                with open(SCHOOL_RULES_FILE, "w",
                          encoding="utf-8") as f:
                    json.dump(data, f, indent=2, sort_keys=True)
                    f.write("\n")
            log_event("portal_school_rules_changed", username=username,
                      changes=changes, school_hours=hours_change)
            self._send_json(200, {
                "ok": True, "school_rules": effective_school_rules(),
                "changed_by": username, "changes": changes,
                "school_hours_changed": hours_change,
            })

        elif self.path == "/portal_chat":
            # Tech-department oversight, part one: an approved
            # tech/admin account can talk to Echo through the portal.
            # It is the same chat as /chat — same STOP behavior, same
            # ticket rule — with the sender's portal username
            # attributed in the activity log.
            username = payload.get("username")
            account = account_for_token(username, payload.get("token"))
            if account is None or not is_admin_account(account):
                log_event("portal_chat_refused", username=username)
                self._send_json(403, {"ok": False, "error":
                    "portal chat is for approved tech/admin portal "
                    "accounts"})
                return
            if is_stopped():
                self._stopped_refusal("/portal_chat")
                return
            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                self._send_json(400, {"ok": False, "error":
                    "portal chat needs a non-empty message"})
                return
            log_event("portal_chat", username=username)
            filed_id = None
            if detect_self_change(message):
                filed_id = file_ticket("self_change", message,
                                       "portal_chat")
            elif detect_app_request(message):
                filed_id = file_ticket(
                    "app_request", app_request_ticket_text(message),
                    "portal_chat")
            try:
                result = ask_brain(brain_messages(
                    [{"role": "user", "content": message}]))
            except Exception as e:
                result = {"ok": False, "error": f"brain call failed: {e}"}
            if filed_id:
                result["ticket_filed"] = filed_id
            result["via"] = "portal"
            result["username"] = username
            log_event("portal_chat_reply", username=username,
                      ok=result.get("ok", False))
            self._send_json(200 if result.get("ok") else 502, result)

        elif self.path == "/portal_home_config":
            # Who sets the Classbook's home-use rules: PARENTS and
            # TECH DEPARTMENTS (Jakob's rule). Students and teachers
            # cannot — teachers keep their approval role; they just
            # don't set home limits. Changes persist to classbook.json
            # (that file IS the settings file — the one deliberate
            # exception to append-only) and every change is logged
            # with who changed it.
            username = payload.get("username")
            account = account_for_token(username, payload.get("token"))
            if account is None or account["status"] != "approved" \
                    or not (account["role"] == "parent"
                            or is_admin_account(account)):
                log_event("portal_home_config_refused",
                          username=username)
                self._send_json(403, {"ok": False, "error":
                    "home-use rules are set by parents and tech/admin "
                    "portal accounts — students and teachers cannot "
                    "change them"})
                return
            wants_limit = "session_limit_minutes" in payload
            wants_enabled = "enabled" in payload
            current = home_use_config()
            if not wants_limit and not wants_enabled:
                log_event("portal_home_config_read", username=username)
                self._send_json(200, {"ok": True, "home_use": current,
                                      "read_by": username})
                return
            new_limit = payload.get("session_limit_minutes")
            if wants_limit and (not isinstance(new_limit, int)
                                or isinstance(new_limit, bool)
                                or new_limit < 0 or new_limit > 600):
                self._send_json(400, {"ok": False, "error":
                    "session_limit_minutes must be a whole number "
                    "from 0 to 600"})
                return
            if wants_enabled \
                    and not isinstance(payload.get("enabled"), bool):
                self._send_json(400, {"ok": False, "error":
                    "enabled must be true or false"})
                return
            data = load_json_file(CLASSBOOK_FILE) or {}
            home = dict(data.get("home_use") or {})
            changes = {}
            if wants_limit:
                changes["session_limit_minutes"] = {
                    "from": current["session_limit_minutes"],
                    "to": new_limit}
                home["session_limit_minutes"] = new_limit
            if wants_enabled:
                changes["enabled"] = {"from": current["enabled"],
                                      "to": payload["enabled"]}
                home["enabled"] = payload["enabled"]
            home.setdefault("homework_check", True)
            data["home_use"] = home
            with open(CLASSBOOK_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            log_event("portal_home_config_changed", username=username,
                      changes=changes)
            self._send_json(200, {"ok": True,
                                  "home_use": home_use_config(),
                                  "changed_by": username,
                                  "changes": changes})

        elif self.path == "/home_session_start":
            # Classbook home use (school_student only): a student at
            # home starts a timed Echo session. Homework comes first —
            # if it isn't done, Echo's reply says so before anything
            # else.
            if current_profile() != "school_student":
                self._send_json(403, {"ok": False, "error":
                    "home sessions are a Classbook feature — they "
                    "exist only under the school_student profile"})
                return
            cfg = home_use_config()
            if not cfg["enabled"]:
                self._send_json(403, {"ok": False, "error":
                    "home use is turned off for this Classbook"})
                return
            student = payload.get("student")
            if not isinstance(student, str) or not student.strip():
                self._send_json(400, {"ok": False, "error":
                    "a home session needs the student's name"})
                return
            student = student.strip()
            homework_done = payload.get("homework_done") is True
            limit = cfg["session_limit_minutes"]
            school_rules = load_school_rules()
            if school_rules["home_limit_default_minutes"] is not None:
                # The school's own default, set under the governance
                # rules, overrides the stored home-use default.
                limit = school_rules["home_limit_default_minutes"]
            homework_first = (not homework_done) \
                and school_rules["homework_first"]
            with _home_lock:
                _home_sessions[student] = {
                    "student": student,
                    "started_monotonic": time.monotonic(),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "limit_minutes": limit,
                    "homework_done": homework_done,
                }
            log_event("home_session_started", student=student,
                      limit_minutes=limit, homework_done=homework_done)
            if homework_first:
                line = (f"Before anything else: you have homework to "
                        f"do. Let's get that done first — your Echo "
                        f"time today is {limit} minutes.")
            elif homework_done:
                line = (f"Homework's done — good. Your Echo time "
                        f"today is {limit} minutes, and the clock "
                        f"starts now.")
            else:
                line = (f"Your Echo time today is {limit} minutes, "
                        f"and the clock starts now.")
            self._send_json(200, {
                "ok": True, "student": student,
                "session_limit_minutes": limit,
                "minutes_left": limit,
                "homework_done": homework_done,
                "homework_first": homework_first,
                "reply": line, "message": line,
            })

        elif self.path == "/home_session_end":
            if current_profile() != "school_student":
                self._send_json(403, {"ok": False, "error":
                    "home sessions are a Classbook feature — they "
                    "exist only under the school_student profile"})
                return
            student = payload.get("student")
            session = end_home_session(student) \
                if isinstance(student, str) else None
            if session is None:
                self._send_json(404, {"ok": False, "error":
                    "no active home session for that student"})
                return
            elapsed = (time.monotonic()
                       - session["started_monotonic"]) / 60
            log_event("home_session_ended", student=student,
                      elapsed_minutes=round(elapsed, 2))
            self._send_json(200, {"ok": True, "student": student,
                                  "state": "ended"})

        else:
            log_event("unknown_route", method="POST", path=self.path)
            self._send_json(404, {"ok": False, "error": "unknown route"})

    def log_message(self, *args):  # keep the console quiet; our log is the file
        pass


if __name__ == "__main__":
    log_event("server_start", version=VERSION, host=HOST, port=PORT)
    print(f"{VERSION} listening on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), EchoHandler).serve_forever()
