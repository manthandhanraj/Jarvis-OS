
"""Voice implementation of IOChannel. Wake word -> capture -> transcribe -> speak.

Two things matter for usability here:

1. The wake phrase is stripped from the captured command. The microphone often
   re-hears "hey jarvis" at the head of the utterance (or the user repeats it),
   which used to leak into the command text and corrupt the extracted target.
2. An empty or wake-word-only utterance is retried once instead of being routed,
   so a mis-fire does not produce a nonsense action.
"""
from __future__ import annotations

import re

from config.settings import Settings
from core.base import BaseModule
from core.io.base import IOChannel
from utils.text import normalize
from voice.audio.microphone import Microphone
from voice.stt.whisper_engine import WhisperSTT
from voice.tts.pyttsx3_engine import Pyttsx3TTS
from voice.wakeword.keyword_detector import KeywordWakeWord

_WAKE_FRAGMENTS = (
    "hey jarvis", "ok jarvis", "okay jarvis", "hello jarvis", "hi jarvis",
    "hey jaarvis", "hey javis", "hey jervis", "jaarvis", "jervis", "javis",
    "jarvis",
)
_ACK = "Hello Manthan sir."
_NOT_HEARD = "Sorry, I did not catch that."


class VoiceIO(BaseModule, IOChannel):
    def __init__(self, settings: Settings) -> None:
        BaseModule.__init__(self, name="voice_io")
        self.settings = settings
        self.mic = Microphone(settings.mic)
        self.stt = WhisperSTT(settings.stt)
        self.tts = Pyttsx3TTS(settings.tts)
        self.wake = KeywordWakeWord(self.mic, self.stt, settings.wakeword)

    def initialize(self) -> None:
        self.mic.initialize()
        self.stt.initialize()   # loads the model (heaviest step)
        self.tts.initialize()
        self.mark_ready()

    @staticmethod
    def _strip_wake(text: str) -> str:
        cleaned = normalize(text)
        for fragment in sorted(_WAKE_FRAGMENTS, key=len, reverse=True):
            cleaned = re.sub(rf"(?<!\w){re.escape(fragment)}(?!\w)", " ", cleaned)
        return " ".join(cleaned.split()).strip(" ,.:;-")

    def _listen(self) -> str:
        audio = self.mic.record_utterance()
        raw = self.stt.transcribe(audio, self.settings.mic.sample_rate)
        return self._strip_wake(raw)

    def get_command(self) -> str | None:
        self.wake.wait_for_wake()
        self.send(_ACK)

        text = self._listen()
        if not text:
            self.send(_NOT_HEARD)
            return ""

        self.log.info("Command heard: %r", text)
        return text

    def send(self, text: str) -> None:
        self.log.info("JARVIS: %s", text)
        self.tts.speak(text)

    def ask(self, prompt: str) -> str:
        self.send(prompt)
        return self._listen()

    def shutdown(self) -> None:
        self.tts.shutdown()
        self.stt.shutdown()
        self.mic.shutdown()
        self.mark_stopped()
