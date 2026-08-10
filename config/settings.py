"""Central configuration for JARVIS OS."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class MicSettings:
    sample_rate: int = 16000
    channels: int = 1
    frame_ms: int = 30
    silence_threshold: float = 0.006
    calibrate_seconds: float = 0.6
    calibration_multiplier: float = 1.4
    start_timeout_s: float = 15.0
    silence_hangover_s: float = 0.9
    max_utterance_s: float = 8.0
    preroll_ms: int = 320


@dataclass(frozen=True)
class STTSettings:
    engine: str = "whisper"
    model_size: str = "base"
    device: str = "auto"
    compute_type: str = "auto"
    language: str | None = "en"
    beam_size: int = 5


@dataclass(frozen=True)
class TTSSettings:
    engine: str = "pyttsx3"
    rate: int = 178
    volume: float = 1.0
    voice_hint: str = "en"


@dataclass(frozen=True)
class WakeWordSettings:
    phrases: tuple[str, ...] = (
        "hey jarvis", "jarvis", "ok jarvis", "hello jarvis", "jaarvis", "hey jaarvis",
    )
    window_s: float = 2.0
    cooldown_s: float = 0.3


@dataclass(frozen=True)
class AutomationSettings:
    volume_step: int = 10
    brightness_step: int = 10
    shutdown_delay_s: int = 20
    restart_delay_s: int = 20
    process_kill_timeout_s: float = 10.0

    protected_processes: tuple[str, ...] = (
        "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
        "lsass.exe", "smss.exe", "system", "svchost.exe", "registry",
    )

    app_aliases: dict[str, str] = field(default_factory=lambda: {
        "chrome": "chrome", "google chrome": "chrome",
        "edge": "msedge", "microsoft edge": "msedge",
        "firefox": "firefox",
        "notepad": "notepad",
        "notepad plus plus": "notepad++", "notepad++": "notepad++",
        "calculator": "calc", "calc": "calc",
        "vs code": "code", "vscode": "code", "code": "code",
        "visual studio code": "code",
        "explorer": "explorer", "file explorer": "explorer", "files": "explorer",
        "cmd": "cmd", "command prompt": "cmd",
        "powershell": "powershell",
        "terminal": "wt", "windows terminal": "wt",
        "task manager": "taskmgr",
        "paint": "mspaint",
        "settings": "ms-settings:", "windows settings": "ms-settings:",
        "control panel": "control",
        "camera": "microsoft.windows.camera:",
        "spotify": "spotify",
        "discord": "discord",
        "steam": "steam",
        "epic": "EpicGamesLauncher", "epic games": "EpicGamesLauncher",
        "word": "winword", "ms word": "winword",
        "excel": "excel", "ms excel": "excel",
        "powerpoint": "powerpnt",
        "vlc": "vlc",
        "telegram": "telegram",
        "whatsapp": "whatsapp",
    })


@dataclass(frozen=True)
class BrowserSettings:
    preferred: str = "chrome"
    default_engine: str = "google"
    youtube_autoplay: bool = True
    fetch_timeout_s: float = 6.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )


@dataclass(frozen=True)
class DevSettings:
    workspace_roots: tuple[str, ...] = (
        r"%USERPROFILE%\Projects",
        r"%USERPROFILE%\Documents",
        r"%USERPROFILE%\Desktop",
        r"%USERPROFILE%\source\repos",
        r"D:\Projects",
    )
    scan_depth: int = 2
    editor_command: str = "code"
    terminal_command: str = "wt"
    cache_file: str = "projects.json"
    cache_ttl_s: int = 900
    match_cutoff: float = 0.5
    ignored_dirs: tuple[str, ...] = (
        "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
        "dist", "build", "target", ".idea", ".vscode", "site-packages",
    )


@dataclass(frozen=True)
class GameSettings:
    riot_client_paths: tuple[str, ...] = (
        r"C:\Riot Games\Riot Client\RiotClientServices.exe",
        r"D:\Riot Games\Riot Client\RiotClientServices.exe",
        r"%ProgramFiles%\Riot Games\Riot Client\RiotClientServices.exe",
    )
    riot_products: dict[str, str] = field(default_factory=lambda: {
        "valorant": "valorant",
        "league of legends": "league_of_legends",
        "lol": "league_of_legends",
        "legends of runeterra": "bacon",
        "teamfight tactics": "league_of_legends",
    })
    cache_file: str = "games.json"
    cache_ttl_s: int = 3600
    match_cutoff: float = 0.5
    scan_timeout_s: float = 25.0


@dataclass(frozen=True)
class BrainSettings:
    enabled: bool = True
    provider: str = "ollama"
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"

    intent_temperature: float = 0.0
    chat_temperature: float = 0.7
    num_ctx: int = 4096
    max_tokens: int = 320

    request_timeout_s: float = 90.0
    health_timeout_s: float = 4.0

    history_turns: int = 6
    min_confidence: float = 0.45
    confirm_below_confidence: float = 0.75

    persona: str = (
        "You are JARVIS, a personal AI assistant running on the user's Windows PC. "
        "The user speaks Hinglish (Roman-script Hindi mixed with English), Hindi or English. "
        "Reply in the same mix the user used, Hinglish by default. "
        "Be brief: one to three sentences unless more detail is asked for. "
        "Be warm, direct and a little witty, never robotic. "
        "You do not perform actions yourself: the system executes commands. "
        "Never claim you opened, closed, launched or changed anything. "
        "If something is outside your abilities, say so plainly."
    )


@dataclass(frozen=True)
class MemorySettings:
    enabled: bool = True
    db_file: str = "jarvis_memory.db"

    context_window: int = 12
    context_prompt_actions: int = 4
    recall_limit: int = 8

    reference_max_age_s: float = 600.0
    remember_confirmation: bool = False


@dataclass(frozen=True)
class FileSettings:
    enabled: bool = True
    search_roots: tuple[str, ...] = (
        r"%USERPROFILE%\Desktop",
        r"%USERPROFILE%\Documents",
        r"%USERPROFILE%\Downloads",
        r"%USERPROFILE%\Pictures",
        r"%USERPROFILE%\Music",
        r"%USERPROFILE%\Videos",
    )
    search_depth: int = 4
    max_results: int = 20
    use_recycle_bin: bool = True
    ignored_dirs: tuple[str, ...] = (
        "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
        "appdata", "$recycle.bin", "system volume information",
    )
    categories: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "Images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"),
        "Videos": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"),
        "Music": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
        "Documents": (".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx",
                      ".xls", ".xlsx", ".odt", ".md", ".rtf"),
        "Archives": (".zip", ".rar", ".7z", ".tar", ".gz"),
        "Programs": (".exe", ".msi", ".bat", ".cmd"),
        "Code": (".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go",
                 ".rs", ".html", ".css", ".json"),
    })


@dataclass(frozen=True)
class GuiSettings:
    title: str = "JARVIS OS"
    width: int = 760
    height: int = 580
    bg: str = "#0b0f1a"
    panel: str = "#131a2b"
    accent: str = "#39d0d8"
    text: str = "#e6edf3"
    muted: str = "#7d8aa5"
    user_color: str = "#9ece6a"
    error_color: str = "#f7768e"
    font_family: str = "Consolas"
    font_size: int = 11
    refresh_ms: int = 2500
    enable_tray: bool = True


@dataclass(frozen=True)
class Settings:
    app_name: str = "JARVIS OS"
    version: str = "0.7.0"
    default_language: str = "hinglish"
    supported_languages: tuple[str, ...] = ("en", "hi", "hinglish")

    base_dir: Path = BASE_DIR
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")

    log_level: int = logging.INFO
    log_file: str = "jarvis.log"

    mic: MicSettings = field(default_factory=MicSettings)
    stt: STTSettings = field(default_factory=STTSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    wakeword: WakeWordSettings = field(default_factory=WakeWordSettings)
    automation: AutomationSettings = field(default_factory=AutomationSettings)
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    dev: DevSettings = field(default_factory=DevSettings)
    games: GameSettings = field(default_factory=GameSettings)
    brain: BrainSettings = field(default_factory=BrainSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    files: FileSettings = field(default_factory=FileSettings)
    gui: GuiSettings = field(default_factory=GuiSettings)

    def __post_init__(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()




