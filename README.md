# JARVIS OS

A modular, offline-first AI assistant for Windows 11. Speaks Hinglish, Hindi
and English. Controls apps, the browser, coding workflows, games, files and the
system — with a local LLM brain, persistent memory, and a GUI dashboard.

Version: **0.7.0** (Day 1 → Day 14)

## Features by day

| Day | Capability |
|-----|------------|
| 1  | Core architecture, lifecycle, logging, settings |
| 2  | Command router + risk-gated confirmations |
| 3  | Offline speech-to-text (faster-whisper) |
| 4  | Text-to-speech (SAPI5 / pyttsx3) |
| 5  | Wake word "Hey Jarvis" + voice I/O |
| 7  | Windows control: apps, volume, brightness, power |
| 8  | Browser: open sites, web search, YouTube |
| 9  | Coding mode: scan projects, VS Code, terminal, run |
| 10 | Gaming: Steam, Epic, Riot, Microsoft Store |
| 11 | AI brain: local LLM (Ollama) for Hinglish intent + chat |
| 12 | Memory: SQLite facts + context, "usko band karo" references |
| 13 | File management: search / open / move / copy / delete / organize |
| 14 | GUI dashboard (Tkinter) + optional system tray |

(Day 6 voice authentication is intentionally deferred.)

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Everything for Days 11–14 uses the standard library (sqlite3, ctypes, tkinter).
Only the voice stack and the optional tray icon need extra packages.

### AI brain (optional but recommended)

Install [Ollama](https://ollama.com), then pull the model:

```powershell
ollama pull qwen2.5:7b-instruct
```

If Ollama is not running, keyword commands still work; only free-form
understanding and chat are disabled.

### System tray (optional)

```powershell
pip install pystray pillow
```

Without these the GUI still runs; closing the window just exits.

## Run

```powershell
python main.py                # text mode (default)
python main.py --mode gui     # GUI dashboard
python main.py --mode voice   # voice mode
python main.py --no-ai        # keyword-only, no LLM
python main.py --no-memory    # disable persistence
```

## Example commands

```
notepad kholo
volume 40 kar do
downloads kholo
resume.pdf ko documents me move karo
downloads organize karo
find file report
delete file old.txt          (asks twice — high risk)
remember my main project is jarvis_os
mera main project kya hai
chrome kholo
usko band karo               (references the last app)
valorant khelo
run jarvis_os
```

## Risk model

| Level  | Confirmations | Examples |
|--------|---------------|----------|
| SAFE   | 0 | open app, volume, search, open/find file, remember |
| MEDIUM | 1 | close app, run project, move/copy, create/organize folder, forget |
| HIGH   | 2 | shutdown, restart, delete file/folder |

The LLM only decides *which* command runs; the risk level always comes from the
command itself, and low-confidence guesses are bumped up a level.

## Layout

```
config/      settings
core/        assistant, router, session, risk, I/O channels
voice/       mic, STT, TTS, wake word
automation/  windows, browser, dev, games, files
brain/        llm, intent, conversation, commands
memory/       SQLite store, context, reference resolution
security/     confirmation flow
gui/          Tkinter dashboard
utils/        logging, text, exceptions
```

File operations are confined to your user folders (Desktop, Documents,
Downloads, Pictures, Music, Videos); deletes go to the Recycle Bin.
