"""Reference -> keyword -> AI routing, with risk gating and memory logging."""
from __future__ import annotations

from brain.ai_brain import AIBrain
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from memory.memory_service import MemoryService
from security.confirmation import Confirmer
from utils.logger import get_logger

_NO_MATCH = "Sorry, I did not understand. Say 'help' for options."


class CommandRouter:
    def __init__(
        self,
        commands: list[Command],
        confirmer: Confirmer,
        ctx: CommandContext,
        brain: AIBrain | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self._commands = list(commands)
        self._by_name = {c.name: c for c in self._commands}
        self._confirmer = confirmer
        self._ctx = ctx
        self._brain = brain
        self._memory = memory
        self.log = get_logger("jarvis.router")

    def route(self, text: str) -> CommandResult:
        if not text or not text.strip():
            return CommandResult("")

        resolved = self._resolve_reference(text)
        if resolved is not None:
            return resolved

        for cmd in self._commands:
            try:
                if not cmd.matches(text):
                    continue
                self.log.info("Keyword match '%s' (%s).", cmd.name, cmd.risk.value)
                return self._dispatch(cmd, text, cmd.risk, text)
            except Exception as exc:  # noqa: BLE001
                self.log.exception("Command '%s' failed.", cmd.name)
                return CommandResult(f"Sorry, '{cmd.name}' error: {exc}")

        return self._ai_fallback(text)

    def _resolve_reference(self, text: str) -> CommandResult | None:
        if self._memory is None or not self._memory.is_ready:
            return None
        hit = self._memory.resolve_reference(text)
        if hit is None:
            return None
        command_name, target = hit
        cmd = self._by_name.get(command_name)
        if cmd is None:
            return None
        canonical = cmd.to_text(target)
        self.log.info("Reference resolved to %s '%s'.", command_name, target)
        return self._dispatch(cmd, canonical, cmd.risk, text)

    def _dispatch(self, cmd: Command, phrase: str, risk: RiskLevel, spoken: str) -> CommandResult:
        if not self._confirmer.confirm(cmd.describe(phrase), risk):
            return CommandResult("Okay, cancelled.")
        result = cmd.execute(phrase, self._ctx)
        self._remember_action(cmd, phrase, spoken, result)
        return result

    def _remember_action(
        self, cmd: Command, phrase: str, spoken: str, result: CommandResult
    ) -> None:
        if self._memory is None or not self._memory.is_ready:
            return
        target = self._target_of(cmd, phrase)
        success = not result.reply.lower().startswith(("sorry", "samajh nahi"))
        self._memory.log_action(
            command=cmd.name, target=target, phrase=spoken, success=success
        )

    @staticmethod
    def _target_of(cmd: Command, phrase: str) -> str:
        """Best-effort argument recovery for the context log."""
        try:
            return cmd.describe(phrase).split("'")[1]
        except (IndexError, AttributeError):
            return ""

    def _ai_fallback(self, text: str) -> CommandResult:
        if self._brain is None or not self._brain.is_ready:
            self.log.info("No command matched and AI brain unavailable: %r", text)
            return CommandResult(_NO_MATCH)

        try:
            intent = self._brain.resolve(text, self._commands)
        except Exception:  # noqa: BLE001
            self.log.exception("Intent resolution failed.")
            return CommandResult(_NO_MATCH)

        if intent.is_chat:
            grounding = self._memory.context_snippet() if self._memory else ""
            try:
                reply = self._brain.chat(text, grounding=grounding)
            except Exception:  # noqa: BLE001
                self.log.exception("Conversation failed.")
                return CommandResult(_NO_MATCH)
            return CommandResult(reply or _NO_MATCH)

        cmd = intent.command
        canonical = cmd.to_text(intent.target)
        risk = self._effective_risk(cmd.risk, intent.confidence)
        self.log.info(
            "AI match '%s' -> %r (confidence %.2f, risk %s).",
            cmd.name, canonical, intent.confidence, risk.value,
        )

        try:
            return self._dispatch(cmd, canonical, risk, text)
        except Exception as exc:  # noqa: BLE001
            self.log.exception("AI-routed command '%s' failed.", cmd.name)
            return CommandResult(f"Sorry, '{cmd.name}' error: {exc}")

    def _effective_risk(self, risk: RiskLevel, confidence: float) -> RiskLevel:
        """A guessed action always needs at least one confirmation."""
        threshold = self._ctx.settings.brain.confirm_below_confidence
        if confidence < threshold and risk is RiskLevel.SAFE:
            return RiskLevel.MEDIUM
        return risk

