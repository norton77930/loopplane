"""The Anthropic (Claude) model-provider adapter (020).

Importable without the ``anthropic`` extra; the SDK is imported lazily when the default
client is built.
"""

from loopplane.adapters.anthropic.adapter import AnthropicModel
from loopplane.adapters.anthropic.config import AnthropicConfig

__all__ = [
    "AnthropicConfig",
    "AnthropicModel",
]
