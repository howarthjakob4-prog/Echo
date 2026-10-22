"""Shared base for Echo's platform plugins (Jakob's plugin pack, 2026-10-19).

One plugin per platform lives beside this file (youtube, facebook,
instagram, x, tiktok). Every plugin is *plumbing only*: the sanctioned
route to its platform is that platform's official API — never website
automation — and in this build NO plugin is connected to any account.
Every action method refuses with a plain reason. No credentials exist
anywhere in this package, and no plugin performs network I/O.

Jakob's rules are enforced here, in the shared base, so no plugin can
opt out of them:

- Picture rule: any attempt to attach media / upload an image or video
  is refused outright — "Echo never uploads pictures." (Read-only
  browsing is Echo's web rule everywhere; media upload is never part
  of a plugin action.)
- Appropriate content only: an action flagged inappropriate is refused
  as outside Echo's rules — outside-rules actions go to Jakob first.
- Grok's deal: inside his rules, Echo may post and reply on his own
  accounts — these plugins are how. The deal does not create accounts:
  a plugin stays "not_connected" until Jakob hooks up that account
  himself.
- Watchability (Jakob's oversight rule): EVERY plugin action attempt
  funnels through `_attempt`, which writes exactly one rich entry to
  Echo's activity log (platform, action, a plain-language summary of
  what was done or attempted, and the outcome: posted / refused /
  failed). There are no silent paths — a refusal is logged with its
  reason, in the open, the same as everything else Echo does.
"""

import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(os.path.dirname(HERE), "activity_log.jsonl")

PICTURE_RULE_REASON = (
    "Echo never uploads pictures — media upload is refused by the "
    "picture rule"
)
OUTSIDE_RULES_REASON = (
    "outside Echo's rules — appropriate content only; anything outside "
    "his rules goes to Jakob first"
)


def _default_log(event, **fields):
    """Append one entry to Echo's activity log. Used when the plugin is
    driven outside the server (the server passes its own log_event,
    which writes the same file in the same format)."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    entry.update(fields)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


class PluginRefused(Exception):
    """A plugin action was refused; `reason` says why, in plain words."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class PlatformPlugin:
    """Uniform contract for every platform plugin.

    Subclasses set the class attributes; all behavior (guards, logging,
    refusals) lives here so the rules cannot drift between platforms.
    """

    name = ""            # registry key, e.g. "x"
    platform = ""        # platform family, e.g. "X"
    display_name = ""    # e.g. "X"
    capabilities = []    # action names this plugin will offer once connected
    api_name = ""        # the official API's name
    api_base = ""        # the official API base URL (data, not a client)
    account_note = ""    # whose account / what route, in plain words
    terms = {}           # the platform's automation/terms essentials, as data

    def __init__(self, log=None):
        self._log = log or _default_log
        # No account is connected in this build. Jakob hooks up each
        # account himself; until then this stays None and every action
        # refuses as not connected.
        self.connected_account = None

    # -- status ------------------------------------------------------
    def status(self):
        """'not_connected' until Jakob connects an account."""
        return "connected" if self.connected_account else "not_connected"

    def info(self):
        return {
            "name": self.name,
            "platform": self.platform,
            "display_name": self.display_name,
            "status": self.status(),
            "capabilities": list(self.capabilities),
            "api": {"name": self.api_name, "base": self.api_base},
            "account_note": self.account_note,
            "terms": dict(self.terms),
        }

    # -- the one funnel every action goes through --------------------
    def _not_connected_reason(self):
        return (
            f"not connected: no {self.display_name} account is hooked "
            "up yet — Jakob connects each account before Echo can use "
            "this plugin"
        )

    def _log_outcome(self, action, summary, outcome, reason=None):
        fields = {
            "plugin": self.name,
            "platform": self.platform,
            "action": action,
            "summary": summary,
            "outcome": outcome,
        }
        if reason:
            fields["reason"] = reason
        self._log("plugin_action", **fields)

    def _attempt(self, action, summary, media=None, appropriate=True):
        """Run Jakob's guards for one action and log its outcome.

        Exactly one rich log entry per attempt, whatever happens.
        Raises PluginRefused with the plain reason on any refusal.
        In this build the connected path does not exist: the
        not-connected guard refuses everything that passes the rules.
        When accounts are wired later, the real API call belongs here,
        logging outcome='posted' on success and outcome='failed' with
        the platform's error on failure.
        """
        if media:
            refusal = PICTURE_RULE_REASON
        elif not appropriate:
            refusal = OUTSIDE_RULES_REASON
        elif self.connected_account is None:
            refusal = self._not_connected_reason()
        else:
            refusal = None
        if refusal is not None:
            self._log_outcome(action, summary, "refused", refusal)
            raise PluginRefused(refusal)
        # Unreachable in this build (no account can be connected yet).
        self._log_outcome(action, summary, "failed",
                          "plugin transport is not built yet")
        raise PluginRefused("plugin transport is not built yet")

    # -- uniform actions ----------------------------------------------
    def _summarize(self, verb, text):
        snippet = " ".join((text or "").split())
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        return f'{verb} on {self.display_name}: "{snippet}"'

    def post(self, text, media=None, appropriate=True):
        """Publish a post. Refuses in this build (see module docstring)."""
        return self._attempt("post", self._summarize("Post", text),
                              media=media, appropriate=appropriate)

    def reply(self, text, target=None, media=None, appropriate=True):
        """Reply to someone. Refuses in this build."""
        summary = self._summarize("Reply", text)
        if target:
            summary += f" (to {target})"
        return self._attempt("reply", summary,
                             media=media, appropriate=appropriate)

    def comment(self, text, target=None, media=None, appropriate=True):
        """Comment on a post/video. Refuses in this build."""
        summary = self._summarize("Comment", text)
        if target:
            summary += f" (on {target})"
        return self._attempt("comment", summary,
                             media=media, appropriate=appropriate)
