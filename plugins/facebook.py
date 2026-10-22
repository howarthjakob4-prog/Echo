"""Facebook plugin — Echo's sanctioned route to Facebook (Meta).

The route is Meta's Graph API, official channels only — never
automating the website. Echo's presence on Meta's platforms is an
official Ferrum Page / brand account ("Echo by Ferrum") administered
by Jakob — never a fake personal profile pretending to be a human.
Grok's deal applies here on Meta's terms: Echo may post and reply on
his own, inside his rules and Meta's terms, and everything he does is
logged and watchable by Jakob.

Not connected in this build: every action refuses plainly (see base).
"""

from .base import PlatformPlugin


class FacebookPlugin(PlatformPlugin):
    name = "facebook"
    platform = "Meta"
    display_name = "Facebook"
    capabilities = ["post", "reply", "comment"]
    api_name = "Meta Graph API"
    api_base = "https://graph.facebook.com/v21.0"
    account_note = (
        "An official Ferrum Page ('Echo by Ferrum') administered by "
        "Jakob — never a personal profile. Jakob connects it himself."
    )
    terms = {
        "page_route_only": (
            "Echo's presence is an official Ferrum Page / brand account "
            "administered by Jakob — never a fake personal profile "
            "pretending to be a human."
        ),
        "official_api_only": (
            "Posting and replying go through Meta's official channels "
            "(the Graph API), never by automating the website."
        ),
        "no_inauthentic_behavior": (
            "No spam, no inauthentic or deceptive behavior; Meta's "
            "Platform Terms and Community Standards apply at all times."
        ),
        "stricter_rule_wins": (
            "If Meta's terms ever conflict with Ferrum's rules, the "
            "stricter one wins and Echo stops and tells Jakob."
        ),
        "watchable": (
            "Everything Echo does on Facebook is logged and watchable "
            "by Jakob — he works in the open there."
        ),
    }
