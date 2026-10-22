# Echo for the Ferrum school program

The school build of Echo: the software for the two machines in Jakob's
Ferrum school program — and nothing outside the program.

- **`classbook.json`** — the **Ferrum Classbook**, the student laptop
  (about $349), Linux-based.
- **`teacher.json`** — the **teacher all-in-one desktop**. It has no
  product name yet; none is invented here.
- **`portal.json`** — the school portal's configuration.
- **`school_hours.json`** — the school's own hours window (editable by
  the school).
- **`portal_accounts.jsonl`** — portal accounts, created at runtime:
  append-only account events, salted password hashes, never plaintext.
- **`school_rules.json`** — the school's own configured rules
  (governance layer, below).
- **`echo_school_addendum.txt`** — what Echo himself knows about the
  school program, in his own rules (below).

The program itself, in Jakob's facts: **$1 one-time per school, US
only, launches with Ferrum.**

## Profiles, not a fork

A school can switch its machines' setup how it wants, so the school
software is not a separate build of Echo. It is a **profile** — an
overlay on the same `../server.py`, selected at startup with the
`ECHO_PROFILE` environment variable:

```
python3 ../server.py                              # standard (default)
ECHO_PROFILE=school_student python3 ../server.py  # a Classbook
ECHO_PROFILE=school_teacher python3 ../server.py  # the teacher desktop
```

With no `ECHO_PROFILE` set, Echo behaves exactly as it always has —
the profile overlay changes nothing. An unknown `ECHO_PROFILE` value
makes the server refuse to start, with an error naming the valid
profiles: Echo does not run under rules nobody defined.

Echo's core mechanics apply in every profile, unchanged: the three
permission tiers (AUTO / ASK FIRST / NEVER), STOP winning over
everything, the append-only activity log, and the ticket rule —
self-change asks and feedback become tickets Jakob reviews himself.

## The two school profiles

### `school_student` — the Classbook (stricter)

The student machine runs Jakob's stricter under-18 rules:

- **`remember` is NEVER.** A student cannot ask Echo to remember
  personal notes. The proposal is refused outright (HTTP 403) with the
  rule named: *"students cannot ask Echo to remember personal notes —
  school_student profile."*
- **`save_lookup` stays ASK FIRST, but the approver is the teacher.**
  A parked page-save is labeled `"approver": "teacher"` — it waits for
  a teacher's approval, not just anyone's.
- **`lookup` stays AUTO**, with the same public-web-only URL rules as
  everywhere else (no localhost, no private network, http/https only).
- **Tickets carry the profile label.** A ticket filed from a Classbook
  is labeled with its source profile (`school_student`), so Jakob can
  see which machine-profile it came from when he reviews the queue.
- **`GET /status` says so honestly**: it shows `"profile":
  "school_student"`, and its doing / not-doing lists state the student
  restrictions in plain words.

### `school_teacher` — the teacher all-in-one desktop

- **Standard tiers.** `lookup` is AUTO, `save_lookup` and `remember`
  park as ASK FIRST, the usual NEVER rules apply — nothing is
  stricter and nothing is looser than standard Echo.
- Parked proposals are labeled `"approver": "teacher"`, matching the
  student profile's page-saves: the teacher is the approver in the
  school program.
- `GET /status` shows `"profile": "school_teacher"`.

## Echo knows the program

The school program is not just rules in the server around Echo —
**Echo himself knows it.** On a school profile, every chat's messages
are prepended with a system message carrying
`echo_school_addendum.txt`: the Ferrum school program and the
Classbook, the three portals and who approves what, the school-hours
portal lock with Echo's exact line, teacher approvals for student
saves, the home-use clock and homework-first, the boot license
agreement, the rule that Ferrum software is removed only with Jakob
Howarth's permission, and the ticket rule for self-changes and
feedback. Right after it, a second system note carries the school's
**current configured rules** (its name for the school, the
homework-first toggle, the home limit, the portal hours), so Echo
knows — and follows — the school's own settings, not just the
defaults. The standard profile gets **no** addendum: its messages
reach the brain exactly as they arrived.

## Three system setups (the school's deployment choice)

Each school machine has **three switchable system setups**, chosen by
the school's tech department, recorded in `classbook.json` /
`teacher.json` as `system_modes` with the active one in `system_mode`
(default `ferrum_linux`). `GET /portal_status` reports the active
mode.

1. **Ferrum Linux** (`ferrum_linux`) — the setup this Echo school
   profile runs in. This is the part being built here.
2. **Windows** (`windows`) — the school's alternative setup for the
   same hardware.
3. **Chromebook-style** (`chromebook_style`) — ChromeOS-like, with
   Google, like an original Chromebook.

Windows and Chromebook-style are the school's other options for the
hardware — machine definitions recorded here, **not** software this
project builds.

## The school portal

The portal is the school's control place for its Echo machines. Three
audiences use it, and each sees only its own layer:

- **Tech / admin** — run the portal, control Echo's power, approve or
  deny portal accounts, talk to Echo through the portal, and see
  Echo's live status **and** the full recent activity log
  (owner/admin-level transparency — Jakob's two-layer rule: status
  for everyone, the full log for admins only).
- **Teachers** — their own separate portal (below): an approvals
  inbox and eyes on their classroom's student activity. Not the admin
  log, not the power controls' admin side — theirs is the classroom.
- **Parents** — one job: with tech departments, they set the
  Classbook's home-use rules (below). Nothing else in the portal is
  theirs to change.

Students have portal *accounts*, but the portal is not theirs to run:
they cannot enter during school hours, and they never hold the power
controls or any settings.

### Portal accounts and the founder bootstrap

Accounts are per-person, set up by the school's tech department their
way (`POST /portal_register` with a username, password, and a role of
`tech`, `teacher`, `student`, or `parent`). Passwords are stored only
as salted PBKDF2 hashes in `portal_accounts.jsonl` — an append-only
event file like the ticket store; account state is computed from the
events, never rewritten.

**Jakob's founder bootstrap rule:** the **first** person to log into a
school's portal automatically gets his approval — that first
successful login auto-approves the account as the portal **admin**,
recorded in the activity log as `portal_first_login_auto_approved`
with approval source *"founder rule (Jakob)"*. Every account after
the bootstrap starts **pending**; an approved admin approves or
denies accounts (`POST /portal_approve` / `POST /portal_deny`,
decided `by` an admin account). Pending or denied accounts cannot
enter the portal (HTTP 403, plain message). A wrong password is a 401.

### School hours and Echo's refusal

`school_hours.json` defines the school's window (days + start/end, in
the server's local time). Defaults are **Mon–Fri 07:30–15:30**;
schools set their own — the file is re-read on every request, so an
edit takes effect at once.

- Teachers and admins may enter the portal **at any time**.
- Students (and anyone with no account) may **not** enter during
  school hours. The refusal is HTTP 403, in Echo's own words, Jakob's
  wording: **"Sorry, you're not allowed in here during school hours."**
- Outside school hours a student may enter, but the **off/on controls
  stay refused for students at all times** — chosen and documented
  here: refused, not view-only. Teachers and admins keep full control
  at all times.

### Power: the real STOP and START

`POST /portal_power` (approved teacher or tech/admin account) drives
Echo's **real** stop/start: turning Echo off is the same stopped state
as `POST /stop` — chat and proposals refuse with the same 409 STOP
behavior — and turning it on restarts work. Every portal entry
attempt, refusal, login, and power action is written to the
append-only activity log.

### Tech-department oversight (the courtesy rule)

Approved tech/admin accounts can **communicate with Echo through the
portal** (`POST /portal_chat` — the same chat, same STOP and ticket
rules, with the sender's portal username attributed in the activity
log) and **see how Echo works** (`GET /portal_echo_view` — Echo's live
status plus the last ~20 activity-log entries).

Jakob's condition: *"as long as they're not busy."* The oversight
view is **read-only observation**: it never interrupts Echo mid-task,
and it never interrupts the tech department's own work. Students and
teachers do not get the log view.

### The teacher portal

Teachers get their own separate portal — `GET /teacher_inbox`:

- **Their approvals inbox**: the parked proposals labeled `approver:
  "teacher"` (student page-saves and the like).
- **Eyes on their classroom**: recent **student activity** — student
  proposals and their outcomes, home sessions, student-filed tickets.
  Deliberately *not* the full admin log.

Students, tech, and parents cannot open the teacher inbox (403; tech
and admins use their own oversight view instead). Authorization is
wired into `/approve` and `/deny`: when the caller identifies as a
teacher account, they may decide **only** proposals labeled
`approver: "teacher"` (403 otherwise); admin/tech accounts may decide
any; deciding with no account named is the direct decision, as before.

## Licensed customization — the governance layer

Echo agrees to and follows the rules **each school sets** within the
program, and school moderators/admins may open this Linux Echo
project and program Echo's school behavior as they see fit — **only
under Jakob's license agreements. Founder rules are the ceiling and
cannot be overridden by school configuration.**

What a school *can* set lives in `school_rules.json`, editable by
approved tech/admin portal accounts through
`POST /portal_school_rules` (readable at `GET /portal_school_rules`):

- the school's display name label (`school_name`),
- the homework-first toggle (`homework_first`),
- a home-limit default override (`home_limit_default_minutes`),
- the school-hours window (written to `school_hours.json`, which the
  rules file references).

What a school can **never** set is not in any school-editable file.
The founder-reserved keys — `license_gate`, `stop_enabled`,
`self_rebuild`, `ticket_review`, `software_removal` — belong to
Jakob Howarth's license. If a `POST /portal_school_rules` payload
tries to set one, the server refuses with HTTP 400 and names the
rule: *it stays under Jakob Howarth's license and cannot be changed
by school configuration.* Accepted rule changes and refused
founder-key attempts are both written to the activity log.
Founder-key attempts also count as **violations on Echo's warning
ladder** for the attempting account (see the main README): three
violations lock the user out, and only an admin unlock clears it.

## Classbook home use

A student using a school Classbook at home can use Echo — under a
strict time limit, with homework taken into account. The rules live
in `classbook.json` under `home_use`: `enabled` (default true),
`session_limit_minutes` (default **60**), `homework_check` (default
true).

- `POST /home_session_start {"student": ..., "homework_done": ...}`
  (school_student profile only) starts a timed session. If the
  homework isn't done, Echo's reply is the homework-first line:
  *"Before anything else: you have homework to do. Let's get that done
  first — your Echo time today is 60 minutes."* If it is done, Echo
  confirms the session and the limit.
- While a session is active, `/chat` replies on the Classbook carry
  `"home_session": {"student": ..., "minutes_left": ...}`.
- When the time runs out, `/chat` refuses (HTTP 403) with Echo's
  wrap-up line — *"That's your Echo time for today — time to wrap up.
  Homework and school come first, so we're closing here. See you
  tomorrow."* — and logs `home_session_limit_reached`.
  `POST /home_session_end` ends a session early (logged).
- In-school use (no home session started) is unaffected, and so are
  the standard and teacher profiles.

**Who sets these rules: parents and tech departments** (Jakob's
rule). An approved parent or tech/admin account may read and set the
limit and the on/off switch through `POST /portal_home_config`; the
change persists to `classbook.json` and is logged in the activity log
with who changed it. Students and teachers cannot change home config
(403) — teachers keep their approval role; they just don't set home
limits.

## Endpoints added by the school build

| Method | Path | Who | What it does |
|--------|------|-----|--------------|
| GET | `/portal_status` | anyone | Profile, active system mode, school hours, in-hours now?, Echo on/off |
| POST | `/portal_register` | tech setup | Create a pending portal account (salted hash stored) |
| POST | `/portal_login` | account holder | Authenticate; first-ever login auto-approves as admin (founder rule) |
| POST | `/portal_enter` | approved accounts | Enter the portal; students refused during school hours, in Echo's words |
| POST | `/portal_power` | teacher, tech/admin | Turn Echo off/on (the real STOP/START) |
| POST | `/portal_approve`, `/portal_deny` | admin | Decide a pending portal account |
| POST | `/portal_chat` | tech/admin | Talk to Echo through the portal (username logged) |
| GET | `/portal_echo_view` | tech/admin | Echo's live status + last ~20 activity-log entries |
| GET | `/teacher_inbox` | teacher | Teacher-labeled pending approvals + recent student activity |
| GET | `/portal_school_rules` | tech/admin | Read the school's configured rules |
| POST | `/portal_school_rules` | tech/admin | Set the school's rules under the license ceiling (founder keys refused by name) |
| POST | `/portal_home_config` | parent, tech/admin | Read/set Classbook home-use limit and switch (persisted, logged) |
| POST | `/home_session_start`, `/home_session_end` | students (Classbook) | Timed home sessions with the homework check |

## Honest limits

- This is the school program's **software profile and portal logic
  running on the Echo server** — the same server, the same endpoints,
  the same log. It is **not a bootable OS image**, not an installer,
  and not device management: nothing here provisions, locks down, or
  remotely controls a real Classbook, and the Windows and
  Chromebook-style setups are recorded choices, not builds.
- A "school" here is one server run per machine/profile choice. There
  are no school accounts above the portal accounts, no classrooms, no
  enrollment, and no live link between a student machine and its
  teacher's machine yet — the teacher-approval label records *who must
  approve*; wiring a real teacher's tap on another machine to a
  student's parked proposal is later work, for Jakob to design.
- Portal sessions are simple in-memory tokens on a localhost server —
  the right size for this stage, not a production sign-in system.
- The profiles and portal change Echo's rules only. They do not touch
  the consumer Echo, the default profile's behavior, or any other
  hardware.
