"""JARVIS OS entry point.

Modes:
  text   (default)  keyboard console
  voice             wake word -> speech
  gui               Tkinter dashboard (+ optional system tray)

Flags: --no-ai (skip local LLM brain), --no-memory (skip persistent memory).
"""
from __future__ import annotations

import argparse
import threading

from automation.windows.service import WindowsAutomationService
from brain.ai_brain import AIBrain
from brain.commands.base import CommandContext
from brain.commands.registry import build_commands
from config.settings import settings
from core.assistant import Assistant
from core.io.base import IOChannel
from core.io.console_io import ConsoleIO
from core.risk import CONFIRMATION_POLICY
from core.router import CommandRouter
from core.session import InteractionSession
from memory.memory_service import MemoryService
from security.confirmation import Confirmer
from utils.logger import get_logger, setup_logging


def _greeting(mode: str, ai_on: bool, mem_on: bool) -> str:
    if mode == "voice":
        return "JARVIS online. Say the wake word: Hey Jarvis."
    if ai_on and mem_on:
        return "JARVIS online. AI brain and memory are active."
    if ai_on:
        return "JARVIS online. AI brain active. Ask me anything."
    return "JARVIS online. Commands are ready."


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS OS")
    parser.add_argument("--mode", choices=["text", "voice", "gui"], default="text")
    parser.add_argument("--no-ai", action="store_true", help="skip the local LLM brain")
    parser.add_argument("--no-memory", action="store_true", help="skip persistent memory")
    args = parser.parse_args()

    setup_logging(settings.log_dir, settings.log_file, settings.log_level)
    log = get_logger("jarvis.main")
    log.info("Booting %s v%s (mode=%s) ...", settings.app_name, settings.version, args.mode)

    assistant = Assistant(settings)
    automation = WindowsAutomationService(settings)
    assistant.register(automation)

    memory: MemoryService | None = None
    if not args.no_memory and settings.memory.enabled:
        memory = MemoryService(settings)
        assistant.register(memory)

    brain: AIBrain | None = None
    if not args.no_ai and settings.brain.enabled:
        brain = AIBrain(settings)
        assistant.register(brain)

    # Build the I/O channel (voice/gui need registration for their lifecycle).
    channel: IOChannel
    gui = None
    if args.mode == "voice":
        from voice.voice_io import VoiceIO
        channel = VoiceIO(settings)
        assistant.register(channel)
    elif args.mode == "gui":
        from gui.dashboard import GuiDashboard
        gui = GuiDashboard(settings, brain=brain, memory=memory)
        assistant.register(gui)
        channel = gui
    else:
        channel = ConsoleIO()

    try:
        assistant.initialize()
    except Exception:  # noqa: BLE001
        log.exception("Initialization failed.")
        assistant.shutdown()
        return

    confirmer = Confirmer(channel, CONFIRMATION_POLICY)
    ctx = CommandContext(settings=settings)
    router = CommandRouter(
        build_commands(automation, memory), confirmer, ctx, brain=brain, memory=memory
    )

    ai_on = brain is not None and brain.is_ready
    mem_on = memory is not None and memory.is_ready
    session = InteractionSession(channel, router, greeting=_greeting(args.mode, ai_on, mem_on))

    if args.mode == "gui" and gui is not None:
        worker = threading.Thread(target=session.run, name="jarvis-session", daemon=True)
        worker.start()
        try:
            gui.run_mainloop()   # blocks on the main thread until the window closes
        finally:
            gui.signal_close()
            worker.join(timeout=3)
            assistant.shutdown()
            log.info("%s stopped.", settings.app_name)
        return

    try:
        session.run()
    except KeyboardInterrupt:
        log.info("Interrupt received.")
    finally:
        assistant.shutdown()
        log.info("%s stopped.", settings.app_name)


if __name__ == "__main__":
    main()

