# Echo — Changelog & builder notices

## Echo Linux server 1.3.2 — October 22, 2026 (Jakob's order: "Normal mode is required to stay on in the beta version")

The echo-linux server (`~/workspace/echo-linux/server.py`, the software version line — separate from the brain, still 3.75) gains the **beta mode lock**:

- While the lock is **on** — the shipped state — the running profile is always standard: the effective mode is **normal** regardless of the saved mode, a flip to school mode via `POST /mode` is refused with **403** ("Normal mode is required on the beta version — the beta mode lock is on, so Echo cannot switch to school mode."), and a chat ask ("switch to school mode") gets the plain server-side refusal "I have to stay in normal mode on the beta version." — no flip, no brain call. Flipping *to* normal stays allowed.
- The lock state is stored as `beta_mode_lock` in `mode_state.json`, beside the mode choice, and survives restarts. A lock that has never been recorded defaults to **on**. `/status` and `GET /mode` both report `beta_mode_lock`.
- The owner lifts or re-applies the lock with `POST /mode {"beta_lock": false}` / `{"beta_lock": true}`. Lifting the lock does not flip the mode — the saved mode takes effect again and switching works as in 1.3.1.
- Verified twice (double-check rule): all six demo beats pass in normal mode in both passes; endpoint and chat school-flip attempts were refused in both passes with the mode staying normal; a service restart came back normal + locked (persistence proven). Server left running in normal mode, lock ON.

## Echo Linux server 1.3.1 — October 22, 2026 (Jakob's order: "switchy modes with school and normal")

The echo-linux server (`~/workspace/echo-linux/server.py`, the software version line — separate from the brain, still 3.75) gains **switchable modes**:

- **Normal mode** = the standard profile. **School mode** = the school_student (Classbook) profile, behavior unchanged.
- Flip with `POST /mode {"mode": "school"|"normal"}`, read with `GET /mode`, or by asking in chat: "switch to normal mode" / "school mode". `/status` now always reports the current `mode`.
- The running profile is resolved at runtime everywhere (brain school addendum, status lists, ticket profile labels, the student remember NEVER rule, home sessions, portal answers), and the choice persists in `mode_state.json` across restarts, winning over the `ECHO_PROFILE` boot default.
- Verified twice (double-check rule): all six demo beats pass in normal mode in both passes; a flip back to school restored the student status lists and the student NEVER rule; a server restart kept the saved normal mode. Server left running in normal mode.

## Version 3.6 — October 15, 2026 (founder directive)

Jakob set Echo's version to **3.6**. This release formally versions the October 15 bug-fix work (found by Oma, applied and verified by Muse) that had shipped inside 3.5:

- **Permission tiers fixed** (echo-by-oma.py): requests involving passwords, API keys, codes, secrets, or credentials are NEVER — and NEVER is now checked first, before ASK and AUTO. Unrecognized text returns UNKNOWN instead of falling through.
- **Android Approve/Deny fixed** (MainActivity.kt): the buttons now replace the message in the list with copy(), so the screen actually updates when a request is approved or denied.

Applied the same day:

- `echo-desktop/package.json` — version 3.6.0
- `agent-source/package.json` — version 3.6.0
- Android project (`echo-android-project`) — versionName "3.6", versionCode 36

**Builder (Claude Code):** keep every Echo component on version 3.6 from here on (this supersedes the 3.5 note below). The standalone-mode / QR-pairing draft (EchoPairing.kt) is still NOT in the buildable Android project — it gets wired in only after the clean 3.6 project builds in Android Studio. Version 4.0 stays planned for November 2026 (see below).


## Version 3.5 — October 15, 2026 (founder directive)

Jakob set Echo's version to **3.5** across the whole product. Applied the same day:

- `echo-desktop/package.json` — version 3.5.0
- `agent-source/package.json` — version 3.5.0
- Android project (`echo-android-project`) — versionName "3.5", versionCode 35

**Builder (Claude Code):** keep every Echo component on version 3.5 from here on. New builds, packages, and releases use 3.5 until Jakob sets a new version. If any file in your working copy still shows an older version (0.1.0 / 0.0.0 / 1.0), update it to match — do not ship mixed versions.

## Bug fixes within 3.5 — October 15, 2026 (fixes by Oma, verified by Muse)

Jakob asked for a bug hunt on Echo, then had Oma make the update. Two real bugs found and fixed:
1. Python starter (echo-by-oma.py): password/api-key requests were landing in the ASK tier; Echo's rules make them NEVER. Now NEVER is checked first, and unrecognized harmless text returns UNKNOWN instead of NEVER.
Jakob's idea, added the same day (draft by Oma: EchoPairing.kt): standalone phone mode (Echo keeps working with the computer off; computer-bound actions queue on-device and run on reconnect) and QR code pairing (owner scans the code shown in Echo on the computer; single-use, short expiry, logged). Spec updated in ECHO-UPDATE-1.md.

2. Android app (MainActivity.kt): Approve/Deny buttons mutated fields on the message object, which Compose never redrew — the buttons stayed on screen. Now the handlers replace the item in the list with copy(), so the state actually updates. (The packaged Android Studio project already carried this fix.)

## Planned — Version 4.0, November 2026 (founder directive, October 15, 2026)

Jakob: in November, Echo moves to **version 4.0**. Until then, everything stays on 3.6. When November comes, bump all components together — desktop 4.0.0, agent 4.0.0, Android versionName "4.0" (versionCode above 35) — and update this changelog. The phone line, restriction round two, and the feature additions in ECHO-PUBLIC-RELEASE.md are the headline work of the 4.0 line.

## Also new since the kits were uploaded (all on this branch)

- `ECHO-UPDATE-1.md` — phone-to-computer control, the Blender plugin, the lookup feature, and the quality bar (advanced, production-quality code and visuals; blockouts are only a starting skeleton).
- `ECHO-QUALITY-BAR.md` — the standalone quality standard.
- `ECHO-PUBLIC-RELEASE.md` — founder spec for a possible public release: permission tiers and restrictions enforced in code, browser & website safety rules, an owner-only admin portal, and feature-based subscriptions with NO usage limits on any tier — Free, Plus $20/month, Studio $30/month, Echo Ultra $50/month. Do not build public sign-up, payments, or a release until Jakob says go.
