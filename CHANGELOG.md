# Echo — Changelog & builder notices

## Version 3.5 — October 15, 2026 (founder directive)

Jakob set Echo's version to **3.5** across the whole product. Applied the same day:

- `echo-desktop/package.json` — version 3.5.0
- `agent-source/package.json` — version 3.5.0
- Android project (`echo-android-project`) — versionName "3.5", versionCode 35

**Builder (Claude Code):** keep every Echo component on version 3.5 from here on. New builds, packages, and releases use 3.5 until Jakob sets a new version. If any file in your working copy still shows an older version (0.1.0 / 0.0.0 / 1.0), update it to match — do not ship mixed versions.

## Also new since the kits were uploaded (all on this branch)

- `ECHO-UPDATE-1.md` — phone-to-computer control, the Blender plugin, the lookup feature, and the quality bar (advanced, production-quality code and visuals; blockouts are only a starting skeleton).
- `ECHO-QUALITY-BAR.md` — the standalone quality standard.
- `ECHO-PUBLIC-RELEASE.md` — founder spec for a possible public release: permission tiers and restrictions enforced in code, browser & website safety rules, an owner-only admin portal, and feature-based subscriptions with NO usage limits on any tier — Free, Plus $20/month, Studio $30/month, Echo Ultra $50/month. Do not build public sign-up, payments, or a release until Jakob says go.
