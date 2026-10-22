"""X plugin — Echo's sanctioned route to X.

The route is the X API, official channels only — never automating the
website. This plugin carries the X-terms essentials from Echo's brain
policy ("ON X SPECIFICALLY") as data: a labeled-AI bio, API-only
posting, no spam or duplicates, X's Rules at all times, and the
stricter rule wins. Grok's deal lives here first — Echo may post and
reply on his own account, inside his rules and X's terms.

Not connected in this build: every action refuses plainly (see base).
"""

from .base import PlatformPlugin


class XPlugin(PlatformPlugin):
    name = "x"
    platform = "X"
    display_name = "X"
    capabilities = ["post", "reply"]
    api_name = "X API v2"
    api_base = "https://api.x.com/2"
    account_note = (
        "Echo's own X account, clearly labeled in its bio as an "
        "automated AI (Echo, an AI assistant by Ferrum). Jakob "
        "connects it himself."
    )
    terms = {
        "labeled_ai": (
            "The account must clearly say in its bio that Echo is an "
            "automated AI (Echo, an AI assistant by Ferrum) — never "
            "present himself as a human."
        ),
        "official_api_only": (
            "Posting and replying go through X's official channels "
            "(the API), never by automating the website."
        ),
        "no_spam_or_duplicates": (
            "No spam, no duplicate or mass posting, no deceptive "
            "behavior, no harassing or manipulating people."
        ),
        "x_rules": (
            "Follow X's Rules and automation policy at all times."
        ),
        "stricter_rule_wins": (
            "If any Ferrum rule and X's terms ever conflict, the "
            "stricter one wins and Echo stops and tells Jakob."
        ),
    }
