"""Custom exception hierarchy for JARVIS OS."""
from __future__ import annotations


class JarvisError(Exception):
    """Base class for all JARVIS OS errors."""


class ModuleInitializationError(JarvisError):
    """Raised when a module fails to initialize."""


class ModuleNotReadyError(JarvisError):
    """Raised when an operation is attempted on an uninitialized module."""


class ConfigurationError(JarvisError):
    """Raised when configuration is invalid or missing."""
