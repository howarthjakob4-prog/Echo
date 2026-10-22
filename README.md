# Echo

**Echo is an AI assistant by Ferrum** — designed and built by Jakob Howarth.
Echo runs as a small server on your own machine, answers through a pluggable
"brain," and follows strict rules: permission tiers for everything it does,
an instant STOP, and a ticket system — Echo never rebuilds or reprograms
itself; change requests become tickets for the maintainer to review.

This is Echo's **first public release** — open source under the
MIT License + Commons Clause: free to use, fork, and change, **but
the software cannot be sold** (see [License](#license)).
Fork it, change it, make it what you feel it should be. Changes to the
official Echo, though, land only through a pull request with maintainer
approval (see [Contributing](#contributing)).

- **Software version:** 1.3.2 (this release)
- **Brain version:** 3.75
- **Status:** public beta. On the beta, **normal mode is required and locked
  on** (see [Modes](#modes)).

## Features

- **Permission tiers** — every action is AUTO (just do it), ASK FIRST
  (parked until approved), or NEVER (refused, with the rule named).
- **STOP wins over everything** — once stopped, Echo refuses all work until
  it is started again.
- **Ticket rule** — Echo never changes itself on request. Self-change asks
  and app requests are filed as tickets for the maintainer to review.
- **The Ferrum agreements are built in** — Echo serves its license,
  privacy policy, and terms (`policies.json`, `GET /policies`) and hands a
  document over in chat when asked.
- **Model registry** — `models.json` is the roster of approved models and
  backends; Echo never pretends an unreleased model is running.
- **Switchable modes (1.3.1)** — normal mode and school mode, switchable at
  runtime (see [Modes](#modes)).
- **Beta mode lock (1.3.2)** — on the beta, normal mode stays on; a flip to
  school mode is refused.
- **Careful web research** — lookups run through a real Google Chrome,
  appropriate sites only, SafeSearch on, and a block list enforced at fetch
  time ("Sorry, this website is blocked.").
- **School program profiles** — `school_student` (the Ferrum Classbook)
  and `school_teacher` profiles, selected with `ECHO_PROFILE`
  (see `school/README.md`).
- **Platform plugins** — `plugins/` carries one plugin per platform
  (YouTube, Facebook, Instagram, X, TikTok), each the sanctioned route for
  that platform.
- **Phone app** — Echo is an actual Android app (source in `android/`),
  not just a web page — build it and it lives on your phone like any
  app. There's also a built-in phone-sized web screen in `phone/`
  (see [Phone setup](#phone-setup)).

## Requirements

- **Operating system: Linux or Windows.**
- **Python 3** — Echo's server uses only the Python standard library.
  There is nothing to `pip install`.
- **Google Chrome** (optional) — only for Echo's web-lookup features,
  which render pages in the real Chrome installed on the machine.
- **Ollama** (optional) — only if you run the included local brain
  (`brain_local.py`); see [Give Echo a brain](#give-echo-a-brain).
- A **brain module** for chat replies — see below. The server itself runs
  without one (status, policies, models, and modes all answer), but
  `/chat` needs a brain to talk back.

## Setup

**Are you on Linux or Windows?**

### If you're on Linux, follow these instructions:

1. Make sure Python 3 is installed. Open a terminal and type:

   ```
   python3 --version
   ```

   If that doesn't print a version, install it (Debian/Ubuntu):

   ```
   sudo apt update && sudo apt install -y python3
   ```

2. Download this repository: the green **Code** button → **Download ZIP**,
   then unzip it. (Or, if you use git:
   `git clone https://github.com/howarthjakob4-prog/Echo.git`)
3. Open the unzipped folder — the one containing `server.py`. Right-click
   inside it and choose **Open in Terminal**. (No such menu entry? Press
   **Ctrl+Alt+T** to open a terminal, then type `cd ` followed by the
   folder's path, e.g. `cd ~/Downloads/Echo-main`, and press Enter.)
4. Start Echo — type this command in that terminal and press Enter:

   ```
   python3 server.py
   ```

   You'll see a line saying Echo is listening on http://127.0.0.1:8790.
   **Leave that terminal open** — closing it (or pressing Ctrl+C) stops
   Echo.
5. Check it's alive: open a **second** terminal tab/window and type:

   ```
   curl http://127.0.0.1:8790/status
   ```

   (Or just open http://127.0.0.1:8790/status in a browser.) You should
   see Echo's status, including its version and current mode.
6. **Accept the license (first run only).** Echo's work endpoints stay
   locked until the Ferrum license on this machine is accepted. Read it
   first — type:

   ```
   curl http://127.0.0.1:8790/license
   ```

   Then accept it (put your own name in place of `your name`):

   ```
   curl -X POST http://127.0.0.1:8790/license_accept -H "Content-Type: application/json" -d '{"by": "your name"}'
   ```

   The acceptance is recorded in `license_state.json` beside `server.py`.
   (Echo also creates `activity_log.jsonl`, `tickets.jsonl`, and
   `mode_state.json` there as it runs — those are its own working files.)

### If you're on Windows, follow these instructions:

1. Install Python 3 from [python.org](https://www.python.org/downloads/).
   On the first install screen, tick **"Add python.exe to PATH"**, then
   finish the install.
2. Download this repository: the green **Code** button → **Download ZIP**,
   then unzip it. (Or, if you use git:
   `git clone https://github.com/howarthjakob4-prog/Echo.git`)
3. Open the unzipped folder — the one containing `server.py` — in File
   Explorer. Click the address bar at the top, type `cmd`, and press
   Enter. A **Command Prompt** window opens right in that folder.
   (Fallback: press **Win+R**, type `cmd`, press Enter, then type
   `cd %USERPROFILE%\Downloads\Echo-main` — the path of your unzipped
   folder — and press Enter.)
4. Start Echo — type this command in the Command Prompt and press Enter:

   ```
   py server.py
   ```

   (If Windows says `py` isn't recognized, type `python server.py`
   instead.) You'll see a line saying Echo is listening on
   http://127.0.0.1:8790. **Leave that window open** — closing it (or
   pressing Ctrl+C) stops Echo.
5. Check it's alive: open http://127.0.0.1:8790/status in a browser. You
   should see Echo's status, including its version and current mode.
6. **Accept the license (first run only).** Echo's work endpoints stay
   locked until the Ferrum license on this machine is accepted. Read it
   at http://127.0.0.1:8790/license in a browser, then open a **second**
   Command Prompt (same folder trick) and type:

   ```
   curl -X POST http://127.0.0.1:8790/license_accept -H "Content-Type: application/json" -d "{\"by\": \"your name\"}"
   ```

   (put your own name in place of `your name`). The acceptance is
   recorded in `license_state.json` beside `server.py`. (Echo also
   creates `activity_log.jsonl`, `tickets.jsonl`, and `mode_state.json`
   there as it runs — those are its own working files.)

### Give Echo a brain

Echo's chat answers come from a **brain module**: a program the server
calls with the conversation as JSON and which prints one JSON line back
(`{"ok": true, "reply": "...", "model": "..."}`). Pick one with the
`ECHO_BRAIN` environment variable — set it in the same terminal/Command
Prompt **before** starting the server (stop Echo with Ctrl+C first if
it's already running):

- **Echo's own local brain** — `brain_local.py`, included in this
  release. It talks to [Ollama](https://ollama.com) on this machine
  (http://127.0.0.1:11434) — no account, no API key, nothing leaves the
  machine.
  1. Install Ollama, then pull a model, e.g. type:
     `ollama pull qwen2.5:0.5b`
     (or set `ECHO_LOCAL_MODEL` to a model you already have.)
  2. Point `PROMPT_FILE` at the top of `brain_local.py` at a text file
     holding the system prompt Echo should run under — your own words
     for who Echo is and its rules.
  3. Start Echo with the local brain:
     - Linux terminal: `ECHO_BRAIN=local python3 server.py`
     - Windows Command Prompt: type `set ECHO_BRAIN=local`, press Enter,
       then type `py server.py`
- **`ECHO_BRAIN=meta`** (the default) — Ferrum's hosted brain module.
  That module is **not part of this open-source release**; unless you
  supply your own brain module at the path `models.json` names for the
  active backend, use the local brain above.

Any program that speaks the same JSON-in / JSON-line-out contract can be
plugged in as a brain — that is how Echo's own brain will slot in later.

### Phone setup

Echo's phone version is an **actual Android app** — not a web page.
Its source lives in the `android/` folder of this repo
(app version 3.6, package `com.example.echoapp`).

**Build the app and put it on your phone:**

1. Install **Android Studio** on your computer (Linux or Windows).
2. Open this repo's `android/` folder in Android Studio and let the
   Gradle sync finish (the first sync downloads the libraries — it
   needs internet).
3. Menu: **Build → Build App Bundle(s) / APK(s) → Build APK(s)**.
   When it finishes, click **locate** — the file is
   `app/build/outputs/apk/debug/app-debug.apk`.
4. Send `app-debug.apk` to your phone (email it to yourself, or USB).
5. On the phone, tap the APK and tap **Install**. If Android asks,
   allow installs from your files app or browser — that's just Android
   checking you meant it. Echo then gets its own icon, like any app.

A ready-made APK download will be attached to this release as soon as
one has been built with the Android toolchain — until then, the build
above is how you get the app.

**The built-in web screen (no build needed):** the Echo server also
ships a phone-sized screen in `phone/`:

1. Start the main Echo server first (the steps above) and leave it
   running — the phone screen talks to it.
2. Open a **new** terminal (Linux) or Command Prompt (Windows, same
   folder trick), move into this folder if you aren't already there,
   and type:
   - Linux: `python3 phone/phone_server.py`
   - Windows: `py phone\phone_server.py`
3. Open **http://127.0.0.1:8798** in a browser. You'll get Echo's screen —
   same design as the computer version, reflowed to a phone column —
   with the conversation, a message box, and a STOP button.

As shipped, the phone server listens on this computer only
(`127.0.0.1:8798`), and it reaches the real Echo server on port 8790 —
nothing is mocked; if Echo is down, the phone screen says so.

## Modes

Since 1.3.1, Echo's two everyday profiles are **switchable modes**:

- **Normal mode** — the standard profile.
- **School mode** — the stricter Classbook student profile.

Flip modes with `POST /mode` (`{"mode": "school"}` or `{"mode": "normal"}`),
read the current one with `GET /mode`, or just ask in chat: *"switch to
normal mode"* / *"school mode"*. The choice is saved in `mode_state.json`
and survives restarts. `/status` always reports the current mode.

**Beta mode lock (1.3.2):** this beta ships with the lock **on** — normal
mode is required on the beta version. While the lock is on, a flip to
school mode is refused by the endpoint (403) and in chat ("I have to stay
in normal mode on the beta version."). The owner lifts or re-applies the
lock with `POST /mode {"beta_lock": false}` / `{"beta_lock": true}`.

A machine's boot profile can also be set with `ECHO_PROFILE`
(`standard`, `school_student`, or `school_teacher`); a saved mode wins
over it.

## Contributing

Echo is open source: **fork it and change it how you want** — your fork is
yours to use, study, and change. One hard rule travels with every copy
and every modified version: **the software cannot be sold** (see
[License](#license)). But changes to the official Echo need **approval**: open a pull
request against `main`, and it merges only after a maintainer review and
approval. `main` is protected for exactly this reason. Please keep
changes focused, and say plainly what they do and why.

## License

MIT + Commons Clause — see [LICENSE](LICENSE). Copyright © 2026
Jakob Howarth / Ferrum. Echo is free to use, fork, and change — **but
the software cannot be sold**: nobody who receives it, in original or
modified form, may sell it, or sell a product or service whose value
derives entirely or substantially from the functionality of the
Software.

Echo is a Ferrum product. The golden dragon shield and the Ferrum and
Echo names remain Ferrum's; the license above covers the code in this
repository.
