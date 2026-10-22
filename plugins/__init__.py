"""Echo's platform plugin pack (Jakob's order, 2026-10-19: "a plugin
for each every item — the whole shebang").

One plugin per platform — YouTube, Facebook (Meta), Instagram, X,
TikTok — each the sanctioned plumbing for its platform: official APIs
only, Jakob's rules enforced in the shared base, every action attempt
logged richly enough for Jakob to watch. Plugins are plumbing, not
permission slips and not accounts: every plugin reports
"not_connected" until Jakob hooks up that platform's account himself.
"""

from .base import PlatformPlugin, PluginRefused  # noqa: F401
from .youtube import YouTubePlugin
from .facebook import FacebookPlugin
from .instagram import InstagramPlugin
from .x import XPlugin
from .tiktok import TikTokPlugin

PLUGIN_CLASSES = [YouTubePlugin, FacebookPlugin, InstagramPlugin,
                  XPlugin, TikTokPlugin]


def load_plugins(log=None):
    """Instantiate the pack, keyed by plugin name, in pack order.

    `log` is the server's log_event; standalone use defaults to the
    base module's writer, which appends to the same activity log.
    """
    return {cls.name: cls(log=log) for cls in PLUGIN_CLASSES}


def plugins_payload(log=None):
    """The GET /plugins body: every plugin and its honest status."""
    plugins = load_plugins(log=log)
    return {
        "ok": True,
        "plugins": [p.info() for p in plugins.values()],
    }
