# Echo — phone screen

The phone version of Echo's own screen (Jakob's order, 2026-10-21): same
design as the computer version (the Brain Test page) — same theme tokens,
fonts, bubbles, header, and composer — reflowed to a phone column only.
No redesign, no re-skin.

## Run

    python3 phone_server.py        # serves 127.0.0.1:8798

Open http://127.0.0.1:8798/ — top bar with Echo's avatar, name and
tagline; conversation area; message input + Send + STOP pinned at the
bottom. `?ask=<question>` sends that question on load (demo/capture
deep link; still a real server round-trip).

## How it reaches Echo

Echo's real server on 127.0.0.1:8790 sends no CORS headers, so — like
the Brain Test page, which reaches the brain through its server — this
page talks same-origin: `phone_server.py` serves the page and
pass-through proxies `GET /status` and `POST /chat` to 8790. The page
uses Echo's canonical contract: `POST /chat` with
`{"messages":[{"role":"user","content":"..."}]}`, reply read from
`{"ok":true,"reply":"...","model":"echo_core"}`. Nothing is mocked;
if Echo is down the page says so.

## Files

- `index.html` — the page (design tokens copied from
  `ts-spaces/echo-brain-test/client/src/theme.css`)
- `avatar.png` — Echo's face, cropped from his real art
  (`echo-brain-test/client/src/assets/echo_full.png`)
- `phone_server.py` — static server + /status & /chat bridge, port 8798
