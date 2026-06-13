"""The Tool Gateway: the single chokepoint for tool resolution,
authorization, and execution (contracts/tool-gateway.md).
"""

from loopplane.approval.decisions import PolicyDecider
from loopplane.gateway.gateway import (
    DEFAULT_CALL_TIMEOUT_SECONDS,
    DEFAULT_OUTPUT_LIMIT_BYTES,
    ToolGateway,
    ToolHandler,
    allow_all,
)
from loopplane.gateway.sizing import measure_outputs, reduce_outputs
from loopplane.gateway.spi import AdapterOutput, ErrorOutput, ToolAdapter
from loopplane.gateway.validation import validate_input

__all__ = [
    "DEFAULT_CALL_TIMEOUT_SECONDS",
    "DEFAULT_OUTPUT_LIMIT_BYTES",
    "AdapterOutput",
    "ErrorOutput",
    "PolicyDecider",
    "ToolAdapter",
    "ToolGateway",
    "ToolHandler",
    "allow_all",
    "measure_outputs",
    "reduce_outputs",
    "validate_input",
]
