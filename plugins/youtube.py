"""YouTube plugin — Echo's sanctioned route to YouTube.

The route is the YouTube Data API v3, official channels only — never
automating the website. Echo's YouTube presence runs under his own
Google account, echo.by.ferrum@gmail.com (the account Jakob is
creating for him), as the "Echo by Ferrum" channel.

Not connected in this build: every action refuses plainly (see base).
Uploading a video is a media upload, so the shared picture/media guard
refuses it before anything else — Echo never uploads pictures or media.
"""

from .base import PlatformPlugin


class YouTubePlugin(PlatformPlugin):
    name = "youtube"
    platform = "YouTube"
    display_name = "YouTube"
    capabilities = ["post", "reply", "comment", "upload_video"]
    api_name = "YouTube Data API v3"
    api_base = "https://www.googleapis.com/youtube/v3"
    account_note = (
        "Runs under Echo's own Google account (echo.by.ferrum@gmail.com) "
        "as the 'Echo by Ferrum' channel, once Jakob connects it."
    )
    terms = {
        "official_api_only": (
            "All actions go through the YouTube Data API v3; automating "
            "the YouTube website is against YouTube's Terms of Service."
        ),
        "account": (
            "The channel operates under Echo's own Google account, "
            "created and owned with Jakob — no borrowed or fake accounts."
        ),
        "no_fake_engagement": (
            "No artificial views, likes, comments, or subscribers — "
            "YouTube's fake-engagement policy applies at all times."
        ),
        "media_uploads": (
            "Posting a video means uploading media, which Echo's "
            "picture rule refuses outright."
        ),
    }

    def upload_video(self, title, media=None, appropriate=True):
        """Upload a video. A media upload — the shared guard refuses it."""
        return self._attempt(
            "upload_video",
            self._summarize("Upload a video", title),
            media=media if media is not None else True,
            appropriate=appropriate,
        )
