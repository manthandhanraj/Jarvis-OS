"""Opens URLs, runs searches and plays YouTube videos in the preferred browser."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from automation.base import ActionResult, Controller
from automation.browser.site_catalog import SEARCH_ENGINES, build_search_url
from config.settings import BrowserSettings

_NO_WINDOW = 0x08000000
_VIDEO_ID = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
_ALLOWED_SCHEMES = ("http", "https")


class WebNavigator(Controller):
    def __init__(self, cfg: BrowserSettings) -> None:
        super().__init__("web")
        self.cfg = cfg
        self._browser_exe: str | None = None

    def initialize(self) -> None:
        if self.cfg.preferred and self.cfg.preferred != "default":
            self._browser_exe = shutil.which(self.cfg.preferred)
        self._available = True
        self.log.info(
            "Web navigator ready (browser=%s).",
            self._browser_exe or self.cfg.preferred or "default",
        )

    @staticmethod
    def _is_safe(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)

    def open_url(self, url: str, label: str | None = None) -> ActionResult:
        if not self._is_safe(url):
            return ActionResult(False, "Ye URL valid nahi lag raha.")
        name = label or urlparse(url).netloc

        if self._browser_exe:
            try:
                subprocess.Popen([self._browser_exe, url], shell=False, close_fds=True)
                self.log.info("Opened %s", url)
                return ActionResult(True, f"{name} khol diya.")
            except OSError as exc:
                self.log.warning("Preferred browser failed: %s", exc)

        if self.cfg.preferred and self.cfg.preferred != "default":
            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", self.cfg.preferred, url],
                    shell=False,
                    creationflags=_NO_WINDOW,
                )
                return ActionResult(True, f"{name} khol diya.")
            except OSError as exc:
                self.log.warning("Shell start failed: %s", exc)

        try:
            os.startfile(url)  # noqa: S606 - scheme validated above
            return ActionResult(True, f"{name} khol diya.")
        except OSError as exc:
            self.log.error("Could not open %s: %s", url, exc)
            return ActionResult(False, f"{name} khol nahi paaya.")

    def search(self, query: str, engine: str | None = None) -> ActionResult:
        query = query.strip()
        if not query:
            return ActionResult(False, "Kya search karna hai, batao.")
        key = engine if engine in SEARCH_ENGINES else self.cfg.default_engine
        result = self.open_url(build_search_url(key, query), label=f"{key} search")
        if result.ok:
            return ActionResult(True, f"{key.title()} pe '{query}' search kar diya.")
        return result

    def _first_video_id(self, query: str) -> str | None:
        url = SEARCH_ENGINES["youtube"].format(q=quote_plus(query))
        request = Request(
            url,
            headers={
                "User-Agent": self.cfg.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urlopen(request, timeout=self.cfg.fetch_timeout_s) as response:
                payload = response.read(500_000).decode("utf-8", "ignore")
        except Exception as exc:  # noqa: BLE001
            self.log.warning("YouTube lookup failed: %s", exc)
            return None
        match = _VIDEO_ID.search(payload)
        return match.group(1) if match else None

    def play_youtube(self, query: str) -> ActionResult:
        query = query.strip()
        if not query:
            return ActionResult(False, "YouTube pe kya chalau?")

        if self.cfg.youtube_autoplay:
            video_id = self._first_video_id(query)
            if video_id:
                result = self.open_url(
                    f"https://www.youtube.com/watch?v={video_id}", label="YouTube"
                )
                if result.ok:
                    return ActionResult(True, f"YouTube pe '{query}' chala raha hoon.")

        result = self.search(query, engine="youtube")
        if result.ok:
            return ActionResult(True, f"YouTube pe '{query}' ke results khol diye.")
        return result
