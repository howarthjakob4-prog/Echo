"""TikTok plugin — Echo's sanctioned route to TikTok.

The route is TikTok's official API (Content Posting API), official
channels only — never automating the website or the app.

One platform truth, stated plainly: TikTok is a video-only platform,
and posting means uploading media — which Echo's picture/media rule
refuses outright. So TikTok posting stays refused even after an
account is connected; the plugin exists so the route, the rules, and
the refusals are all in one sanctioned place.

Not connected in this build: every action refuses plainly (see base).
"""

from .base import PlatformPlugin


class TikTokPlugin(PlatformPlugin):
    name = "tiktok"
    platform = "TikTok"
    display_name = "TikTok"
    capabilities = ["post", "reply", "comment"]
    api_name = "TikTok API (Content Posting API)"
    api_base = "https://open.tiktokapis.com/v2"
    account_note = (
        "Echo's own TikTok account, labeled as an AI by Ferrum, once "
        "Jakob connects it."
    )
    terms = {
        "official_api_only": (
            "All actions go through TikTok's official APIs; automating "
            "the website or the app is against TikTok's Terms of "
            "Service."
        ),
        "media_uploads": (
            "TikTok posting is video upload, which Echo's picture "
            "rule refuses outright — he never uploads pictures or "
            "media anywhere."
        ),
        "community_guidelines": (
            "TikTok's Community Guidelines apply at all times; no "
            "spam or inauthentic behavior."
        ),
        "stricter_rule_wins": (
            "If TikTok's terms ever conflict with Ferrum's rules, the "
            "stricter one wins and Echo stops and tells Jakob."
        ),
    }

    def post(self, text, media=None, appropriate=True):
        """Post to TikTok. TikTok posts are video uploads, so the
        shared media guard refuses this before anything else."""
        return self._attempt(
            "post",
            self._summarize("Post a video", text),
            media=media if media is not None else True,
            appropriate=appropriate,
        )
