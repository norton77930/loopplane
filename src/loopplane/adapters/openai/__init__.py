"""The OpenAI (GPT) model-provider adapter (020).

Importable without the ``openai`` extra; the SDK is imported lazily when the default
client is built.
"""

from loopplane.adapters.openai.adapter import OpenAIModel
from loopplane.adapters.openai.config import OpenAIConfig

__all__ = [
    "OpenAIConfig",
    "OpenAIModel",
]
