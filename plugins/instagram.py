"""Instagram plugin — Echo's sanctioned route to Instagram (Meta).

The route is the Instagram Graph API (through Meta), official channels
only — never automating the website or the app. Like Facebook, Echo's
presence is a brand account ("Echo by Ferrum") linked to the official
Ferrum Page and administered by Jakob — never a fake personal profile.
Grok's deal applies here on Meta's terms, and everything Echo does is
logged and watchable by Jakob.

One platform truth, stated plainly: Instagram is an image-first
platform, and Echo's picture rule refuses every image upload — so
image posting stays refused even after an account is connected.

Not connected in this build: every action refuses plainly (see base).
"""

from .base import PlatformPlugin


class InstagramPlugin(PlatformPlugin):
    name = "instagram"
    platform = "Meta"
    display_name = "Instagram"
    capabilities = ["post", "reply", "comment"]
    api_name = "Instagram Graph API (via Meta Graph API)"
    api_base = "https://graph.facebook.com/v21.0"
    account_note = (
        "A brand account ('Echo by Ferrum') linked to the official "
        "Ferrum Page, administered by Jakob — never a personal "
        "profile. Jakob connects it himself."
    )
    terms = {
        "page_route_only": (
            "Echo's presence is a brand account linked to the official "
            "Ferrum Page, administered by Jakob — never a fake "
            "personal profile pretending to be a human."
        ),
        "official_api_only": (
            "Posting and replying go through Meta's official channels "
            "(the Instagram Graph API), never by automating the "
            "website or the app."
        ),
        "no_inauthentic_behavior": (
            "No spam, no inauthentic or deceptive behavior; Meta's "
            "Platform Terms and Community Standards apply at all times."
        ),
        "picture_rule": (
            "Instagram is image-first, and Echo never uploads "
            "pictures — image posting is refused by the picture rule "
            "regardless of connection."
        ),
        "stricter_rule_wins": (
            "If Meta's terms ever conflict with Ferrum's rules, the "
            "stricter one wins and Echo stops and tells Jakob."
        ),
        "watchable": (
            "Everything Echo does on Instagram is logged and "
            "watchable by Jakob — he works in the open there."
        ),
    }
