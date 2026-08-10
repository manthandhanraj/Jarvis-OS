"""Language-agnostic text helpers (en / hi / hinglish)."""
from __future__ import annotations

import re
from collections.abc import Iterable

_AFFIRMATIVE = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "proceed",
    "go", "do", "haan", "han", "haa", "ha", "ji", "jee", "karo", "kardo", "kar",
    "theek", "thik", "bilkul", "zaroor", "sahi",
}
_NEGATIVE = {
    "no", "nope", "nah", "cancel", "stop", "abort", "dont", "don't", "mat", "nahi",
    "nahin", "na", "ruko", "ruk", "band", "rehne", "chodo", "rehne do",
}

FILLER_WORDS: frozenset[str] = frozenset({
    "app", "apps", "application", "program", "please", "jarvis", "karo", "kar",
    "kardo", "kro", "do", "de", "dijiye", "dedo", "zara", "mera", "meri", "the",
    "a", "an", "up", "ko", "me", "my", "pe", "par", "abhi", "jaldi", "hai", "hain",
    "mujhe", "muje", "chahiye", "mein", "main", "ka", "ki", "ke", "se", "wala",
    "wali", "ek", "koi", "sa", "si",
})

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9\u0900-\u097F']+")
_NUMBER = re.compile(r"\b(\d{1,3})\b")


def normalize(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(normalize(text)))


def has_keyword(text: str, keywords: Iterable[str]) -> bool:
    """Word-boundary aware keyword match (prevents 'note' matching 'notepad')."""
    t = normalize(text)
    for kw in keywords:
        kw = kw.strip().lower()
        if not kw:
            continue
        if " " in kw:
            if kw in t:
                return True
        elif re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", t):
            return True
    return False


def strip_triggers(
    text: str,
    triggers: Iterable[str],
    drop_filler: bool = True,
    extra_filler: Iterable[str] = (),
) -> str:
    """Remove trigger phrases (longest first) and return the remaining target."""
    cleaned = normalize(text)
    for trigger in sorted({t.strip().lower() for t in triggers if t.strip()},
                          key=len, reverse=True):
        cleaned = re.sub(rf"(?<!\w){re.escape(trigger)}(?!\w)", " ", cleaned)

    words = cleaned.split()
    if drop_filler:
        blocked = FILLER_WORDS | {w.lower() for w in extra_filler}
        words = [w for w in words if w not in blocked]
    return " ".join(words).strip(" :,-")


def extract_percent(text: str, low: int = 0, high: int = 100) -> int | None:
    """Return the first integer in range, else None."""
    for raw in _NUMBER.findall(normalize(text)):
        value = int(raw)
        if low <= value <= high:
            return value
    return None


def is_affirmative(text: str) -> bool:
    if normalize(text) in _AFFIRMATIVE:
        return True
    toks = tokens(text)
    return bool(toks & _AFFIRMATIVE) and not (toks & _NEGATIVE)


def is_negative(text: str) -> bool:
    return bool(tokens(text) & _NEGATIVE)
