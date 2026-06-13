"""The Internal Tool Adapter and the baseline tool set (FR-030–FR-034):
file reading, file writing with the stale-write guard, content search,
command execution, and asking the user a question — each reachable only
through the Gateway.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import anyio

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.events.envelope import Question
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.memory.store import MemoryEntry, MemoryStore
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock

_SEARCH_MATCH_LIMIT = 100

_DESCRIPTORS = [
    ToolDescriptor(
        name="read_file",
        description="Read a text file and return its content.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        concurrency_safe=True,
        read_only=True,
    ),
    ToolDescriptor(
        name="write_file",
        description=(
            "Write or overwrite a text file. Overwriting an existing file "
            "requires that it was read in this session and has not changed "
            "since that read; creating a new file is exempt."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="search_files",
        description=(
            "Search files under a directory for lines containing a substring."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        concurrency_safe=True,
        read_only=True,
    ),
    ToolDescriptor(
        name="run_command",
        description="Run a shell command inside the working scope.",
        input_schema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    ),
    ToolDescriptor(
        name="ask_user",
        description="Ask the user one or more structured questions.",
        input_schema={
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                }
            },
            "required": ["questions"],
            "additionalProperties": False,
        },
    ),
]


_MEMORY_WRITE_DESCRIPTOR = ToolDescriptor(
    name="memory_write",
    description="Create or update a durable memory entry.",
    input_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["name", "description", "body"],
        "additionalProperties": False,
    },
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _PathOutsideScopeError(ValueError):
    """The requested path resolves outside the run's working scope."""


class InternalToolAdapter:
    def __init__(self, *, memory_store: MemoryStore | None = None) -> None:
        # (session_id, resolved path) -> content digest at the last read.
        self._reads: dict[tuple[str, str], str] = {}
        self._memory = memory_store

    def describe(self) -> Sequence[ToolDescriptor]:
        descriptors = list(_DESCRIPTORS)
        if self._memory is not None:
            descriptors.append(_MEMORY_WRITE_DESCRIPTOR)
        return descriptors

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "search_files": self._search_files,
            "run_command": self._run_command,
            "ask_user": self._ask_user,
            "memory_write": self._memory_write,
        }
        async for output in handlers[name](call_input, context):
            yield output

    async def shutdown(self) -> None:
        self._reads.clear()

    def _resolve(self, context: RunContext, raw: str) -> Path:
        """Resolve a tool-supplied path, confined to the run's working scope.

        Relative paths are joined to the scope; absolute paths and `..`
        escapes that land outside the scope are rejected, so the baseline
        file tools cannot read or write arbitrary locations on the host.
        """
        scope = context.working_scope.resolve()
        candidate = Path(raw)
        target = (candidate if candidate.is_absolute() else scope / candidate).resolve()
        if not target.is_relative_to(scope):
            raise _PathOutsideScopeError(f"{raw} resolves outside the working scope")
        return target

    async def _read_file(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        raw = str(call_input["path"])
        try:
            target = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        try:
            data = target.read_bytes()
        except OSError as exc:
            yield ErrorOutput(message=f"cannot read {raw}: {exc}")
            return
        self._reads[(context.session_id, str(target))] = _digest(data)
        yield TextBlock(text=data.decode("utf-8", errors="replace"))

    async def _write_file(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        raw = str(call_input["path"])
        content = str(call_input["content"])
        try:
            target = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        key = (context.session_id, str(target))
        if target.exists():
            # The stale-write guard (FR-034); new-file creation is exempt.
            recorded = self._reads.get(key)
            if recorded is None:
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=(
                        f"stale write rejected: {raw} exists but was not "
                        f"read in this session"
                    ),
                )
                return
            try:
                current = _digest(target.read_bytes())
            except OSError as exc:
                yield ErrorOutput(message=f"cannot write {raw}: {exc}")
                return
            if current != recorded:
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=(
                        f"stale write rejected: {raw} changed since it was "
                        f"last read in this session"
                    ),
                )
                return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            yield ErrorOutput(message=f"cannot write {raw}: {exc}")
            return
        self._reads[key] = _digest(content.encode("utf-8"))
        yield TextBlock(text=f"wrote {len(content)} characters to {raw}")

    async def _search_files(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        pattern = str(call_input["pattern"])
        raw = str(call_input.get("path", "."))
        try:
            root = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        if not root.is_dir():
            yield ErrorOutput(message=f"not a directory: {raw}")
            return
        matches: list[str] = []
        for path in sorted(root.rglob("*")):
            if len(matches) >= _SEARCH_MATCH_LIMIT or not path.is_file():
                continue
            try:
                text = path.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.relative_to(root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern in line:
                    matches.append(f"{relative}:{line_number}: {line.strip()}")
                    if len(matches) >= _SEARCH_MATCH_LIMIT:
                        break
        if matches:
            yield TextBlock(text="\n".join(matches))
        else:
            yield TextBlock(text=f"no matches for {pattern!r}")

    async def _run_command(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        command = str(call_input["command"])
        try:
            completed = await anyio.run_process(
                command, cwd=context.working_scope, check=False
            )
        except OSError as exc:
            yield ErrorOutput(message=f"cannot run command: {exc}")
            return
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        if stdout.strip():
            yield TextBlock(text=stdout)
        if completed.returncode != 0:
            yield ErrorOutput(
                message=(
                    f"command failed with exit code {completed.returncode}: "
                    f"{stderr.strip() or '(no stderr)'}"
                )
            )

    async def _memory_write(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """The agent-writable memory path (FR-074): there is no privileged
        write — every update traverses the full Gateway pipeline.
        """
        if self._memory is None:
            yield ErrorOutput(message="memory is not enabled for this runtime")
            return
        entry = MemoryEntry(
            type=str(call_input.get("type", "reference")),
            name=str(call_input["name"]),
            description=str(call_input["description"]),
            body=str(call_input["body"]),
        )
        self._memory.write(entry)
        yield TextBlock(text=f"memory entry {entry.name!r} saved")

    async def _ask_user(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        broker = context.interactions
        if broker is None:
            yield ErrorOutput(message="no user is available to answer questions")
            return
        raw_questions = call_input["questions"]
        assert isinstance(raw_questions, list)
        questions = [Question.model_validate(item) for item in raw_questions]
        answers = await broker.ask_question(questions)
        if answers is None:
            yield ErrorOutput(
                message="the question was not answered (no user attached or cancelled)"
            )
            return
        yield TextBlock(text="\n".join(answers))
