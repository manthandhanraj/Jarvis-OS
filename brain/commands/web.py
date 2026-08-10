"""Browser automation commands (sites, search, YouTube).

Ordering rule enforced here: an explicit "open <site>" must open the site, not
start a media search. YouTubePlayCommand therefore requires a play verb AND
refuses to fire when the sentence is an open/launch request without a media
word, and OpenSiteCommand is registered first.
"""
from __future__ import annotations

from automation.browser.site_catalog import find_engine, find_site
from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import has_keyword, strip_triggers

_ACTION_WORDS = ("karo", "kar", "kro", "do", "de", "dijiye", "zara", "please", "jarvis")
_OPEN_VERBS = (
    "open", "kholo", "khol", "khol do", "launch", "start", "chalu karo",
    "visit", "go to", "jao", "dikhao", "show",
)


class _WebCommand(Command):
    def __init__(self, service: WindowsAutomationService) -> None:
        self.service = service


class OpenSiteCommand(_WebCommand):
    name = "open_site"
    description = "Open a known website"
    risk = RiskLevel.SAFE
    canonical = "open {target}"
    target_hint = "site name: youtube, gmail, linkedin, github, leetcode, netflix, amazon"

    _MEDIA = ("song", "gaana", "gana", "music", "video", "track", "playlist")
    _PLAY = ("play", "chalao", "chala do", "chala", "bajao", "baja do", "sunao", "suna do")

    def matches(self, text: str) -> bool:
        if find_site(text) is None:
            return False
        if has_keyword(text, self._PLAY) and has_keyword(text, self._MEDIA):
            return False
        # Bare site name ("youtube") or an explicit open request both qualify.
        return True

    def describe(self, text: str) -> str:
        site = find_site(text)
        return f"Open {site[0]}" if site else self.description

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        site = find_site(text)
        if site is None:
            return CommandResult("Which website should I open?")
        name, url = site
        return CommandResult(self.service.web.open_url(url, label=name.title()).message)


class YouTubePlayCommand(_WebCommand):
    name = "youtube_play"
    description = "Play a song or video on YouTube"
    risk = RiskLevel.SAFE
    canonical = "play {target} on youtube"
    target_hint = "the song, artist or video name to play"

    _PLAY = ("play", "chalao", "chala do", "chala", "bajao", "baja do", "sunao", "suna do")
    _MEDIA = ("song", "gaana", "gana", "music", "video", "track", "playlist")
    _TRIGGERS = (
        "youtube pe", "youtube par", "youtube mein", "youtube", "on youtube",
        "play", "chalao", "chala do", "chala", "bajao", "baja do", "sunao", "suna do",
        "song", "gaana", "gana", "music", "video", "ka", "wala", "hey",
    ) + _ACTION_WORDS

    def matches(self, text: str) -> bool:
        if not has_keyword(text, self._PLAY):
            return False
        if has_keyword(text, _OPEN_VERBS) and not has_keyword(text, self._MEDIA):
            return False
        return has_keyword(text, ("youtube",)) or has_keyword(text, self._MEDIA)

    def describe(self, text: str) -> str:
        return f"Play '{strip_triggers(text, self._TRIGGERS)}' on YouTube"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        query = strip_triggers(text, self._TRIGGERS)
        if not query:
            return CommandResult("What should I play on YouTube?")
        return CommandResult(self.service.web.play_youtube(query).message)


class WebSearchCommand(_WebCommand):
    name = "web_search"
    description = "Search the web in the browser"
    risk = RiskLevel.SAFE
    canonical = "search {target}"
    target_hint = "the search query"

    _SEARCH = ("search", "google kar", "dhundo", "dhoondo", "khojo", "look up", "find out")
    _TRIGGERS = (
        "search karo", "search kar", "search for", "search",
        "google pe", "google par", "google mein", "google kar", "google",
        "youtube pe", "youtube par", "youtube",
        "wikipedia pe", "wikipedia par", "wikipedia",
        "github pe", "github",
        "amazon pe", "amazon",
        "flipkart pe", "flipkart",
        "linkedin pe", "linkedin",
        "maps pe", "maps",
        "stackoverflow pe", "stackoverflow",
        "dhundo", "dhoondo", "khojo", "look up", "find out", "about", "ke bare mein",
        "hey",
    ) + _ACTION_WORDS

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._SEARCH)

    def describe(self, text: str) -> str:
        return f"Search for '{strip_triggers(text, self._TRIGGERS, drop_filler=False)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        query = strip_triggers(text, self._TRIGGERS, drop_filler=False)
        engine = find_engine(text) or ctx.settings.browser.default_engine
        if not query:
            return CommandResult("What should I search for?")
        return CommandResult(self.service.web.search(query, engine=engine).message)


def build_web_commands(service: WindowsAutomationService) -> list[Command]:
    """Site first, then media playback, then generic search."""
    return [
        OpenSiteCommand(service),
        YouTubePlayCommand(service),
        WebSearchCommand(service),
    ]
