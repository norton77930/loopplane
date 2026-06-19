"""The native Google Gemini model-provider adapter (037).

Importable without the ``gemini`` extra; the SDK is imported lazily when the default
client is built.
"""

from loopplane.adapters.gemini.adapter import GeminiModel
from loopplane.adapters.gemini.config import GeminiConfig

__all__ = [
    "GeminiConfig",
    "GeminiModel",
]
