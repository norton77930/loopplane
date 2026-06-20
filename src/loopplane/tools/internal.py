"""The Internal Tool Adapter and the baseline tool set (FR-030–FR-034):
file reading, file writing with the stale-write guard, content search,
command execution, and asking the user a question — each reachable only
through the Gateway.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.events.envelope import Question
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.memory.store import MemoryEntry, MemoryStore
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock
from loopplane.tools.execution import CommandExecutor, HostCommandExecutor

_SEARCH_MATCH_LIMIT = 100

_MAX_TODO_ITEMS = 100

_TODO_STATUSES = ("pending", "in_progress", "completed")

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
        name="edit_file",
        description=(
            "Replace a uniquely-occurring substring in an existing text file. "
            "The file must have been read in this session and be unchanged "
            "since that read; old_string must occur exactly once and must "
            "differ from new_string."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
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
        name="glob_files",
        description=(
            "List files under the working scope whose path matches a glob "
            "pattern (for example '**/*.py'); returns scope-relative paths."
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
        name="grep",
        description=(
            "Search file contents by regular expression within the working "
            "scope. output_mode is one of 'content' (matching lines), "
            "'files_with_matches' (matching paths), or 'count' (number of "
            "matching lines per file); it defaults to 'content'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "output_mode": {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count"],
                },
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
    ToolDescriptor(
        name="exit_plan_mode",
        description=(
            "Submit a proposed plan for the user to approve before executing. "
            "Use this only after read-only investigation: pass the plan as text; "
            "on approval the agent leaves plan mode and may use all tools, on "
            "rejection it stays in plan mode."
        ),
        input_schema={
            "type": "object",
            "properties": {"plan": {"type": "string"}},
            "required": ["plan"],
            "additionalProperties": False,
        },
        # Not read-only: it mutates run state (clears plan mode on approval) and
        # requests a human decision. The plan-mode policy allowlists it by name so it
        # stays callable while planning (spec 038).
    ),
    ToolDescriptor(
        name="todo_write",
        description=(
            "Record the agent's task list for this run. Replaces the current "
            "list with the provided items; each item has a short 'content' and "
            "a 'status' of 'pending', 'in_progress', or 'completed'. Submit an "
            "empty list to clear it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["todos"],
            "additionalProperties": False,
        },
        # Not read-only: it mutates per-run state (the session's todo list).
    ),
    ToolDescriptor(
        name="notebook_edit",
        description=(
            "Edit a Jupyter notebook (.ipynb) cell within the working scope: "
            "replace a cell's source, insert a new code/markdown cell, or delete a "
            "cell, selected by index (mode is 'replace', 'insert', or 'delete'). The "
            "notebook must have been read in this session and be unchanged since."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["replace", "insert", "delete"],
                },
                "index": {"type": "integer", "minimum": 0},
                "source": {"type": "string"},
                "cell_type": {"type": "string", "enum": ["code", "markdown"]},
            },
            "required": ["path", "mode", "index"],
            "additionalProperties": False,
        },
        # Not read-only: it mutates the notebook file.
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


_UNDO_FILE_DESCRIPTOR = ToolDescriptor(
    name="undo_file",
    description=(
        "Undo the most recent change this run made to a file (write_file / "
        "edit_file / notebook_edit), restoring its previous content. Pass the same "
        "'path'; call again to walk back further. Reports when nothing is left to undo."
    ),
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _PathOutsideScopeError(ValueError):
    """The requested path resolves outside the run's working scope."""


class InternalToolAdapter:
    def __init__(
        self,
        *,
        memory_store: MemoryStore | None = None,
        max_file_snapshots: int = 0,
        command_executor: CommandExecutor | None = None,
    ) -> None:
        # (session_id, resolved path) -> content digest at the last read.
        self._reads: dict[tuple[str, str], str] = {}
        self._memory = memory_store
        # The run_command execution seam (spec 052; ADR 0004): None -> the host executor
        # (the current anyio.run_process call verbatim, byte-identical); a
        # LocalJailCommandExecutor sandboxes it. Caller-injected like memory_store
        # (InternalToolAdapter is passed via RuntimeConfig.tool_adapters).
        self._executor = command_executor or HostCommandExecutor()
        # (session_id) -> the session's current todo list (spec 044).
        self._todos: dict[str, list[dict[str, str]]] = {}
        # File-edit undo (spec 054): a bounded, run-scoped, insertion-ordered log of
        # ((session_id, resolved path), prior raw bytes) snapshots taken before a
        # mutating tool overwrites an existing file. 0 (default) = off, byte-identical
        # (no snapshot side-effect, undo_file not registered); the oldest snapshot is
        # dropped once the cap is exceeded (the memory guard). Caller-injected like
        # memory_store (InternalToolAdapter is passed via RuntimeConfig.tool_adapters).
        self._max_file_snapshots = max_file_snapshots
        self._snapshots: list[tuple[tuple[str, str], bytes]] = []

    def describe(self) -> Sequence[ToolDescriptor]:
        descriptors = list(_DESCRIPTORS)
        if self._memory is not None:
            descriptors.append(_MEMORY_WRITE_DESCRIPTOR)
        if self._max_file_snapshots > 0:
            descriptors.append(_UNDO_FILE_DESCRIPTOR)
        return descriptors

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "search_files": self._search_files,
            "glob_files": self._glob_files,
            "grep": self._grep,
            "run_command": self._run_command,
            "ask_user": self._ask_user,
            "exit_plan_mode": self._exit_plan_mode,
            "memory_write": self._memory_write,
            "todo_write": self._todo_write,
            "notebook_edit": self._notebook_edit,
            "undo_file": self._undo_file,
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

    def _snapshot(self, key: tuple[str, str], prior: bytes) -> None:
        """Record a file's prior bytes before a mutating overwrite (spec 054). A no-op
        when undo is disabled (cap 0), so the mutating tools stay byte-identical;
        bounded — the oldest snapshot is dropped once the per-run cap is exceeded."""
        if self._max_file_snapshots <= 0:
            return
        self._snapshots.append((key, prior))
        while len(self._snapshots) > self._max_file_snapshots:
            self._snapshots.pop(0)

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
        prior_bytes: bytes | None = None
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
                prior_bytes = target.read_bytes()
            except OSError as exc:
                yield ErrorOutput(message=f"cannot write {raw}: {exc}")
                return
            if _digest(prior_bytes) != recorded:
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
        if prior_bytes is not None:
            # Snapshot the overwritten file's prior bytes for undo (spec 054).
            self._snapshot(key, prior_bytes)
        self._reads[key] = _digest(content.encode("utf-8"))
        yield TextBlock(text=f"wrote {len(content)} characters to {raw}")

    async def _edit_file(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """Replace a uniquely-occurring substring in an existing file, gated by
        the same stale-write guard as `_write_file` (FR-002, FR-003): the file
        must have been read this session and be unchanged since.
        """
        raw = str(call_input["path"])
        old_string = str(call_input["old_string"])
        new_string = str(call_input["new_string"])
        if old_string == new_string:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    "old_string and new_string are identical; no change requested"
                ),
            )
            return
        try:
            target = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        try:
            data = target.read_bytes()
        except OSError as exc:
            yield ErrorOutput(message=f"cannot edit {raw}: {exc}")
            return
        key = (context.session_id, str(target))
        recorded = self._reads.get(key)
        if recorded is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"stale edit rejected: {raw} exists but was not read in "
                    f"this session"
                ),
            )
            return
        if _digest(data) != recorded:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"stale edit rejected: {raw} changed since it was last "
                    f"read in this session"
                ),
            )
            return
        text = data.decode("utf-8", errors="replace")
        occurrences = text.count(old_string)
        if occurrences == 0:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"old_string not found in {raw}",
            )
            return
        if occurrences > 1:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"old_string is not unique in {raw} ({occurrences} "
                    f"occurrences); add surrounding context to disambiguate"
                ),
            )
            return
        updated = text.replace(old_string, new_string, 1)
        try:
            target.write_text(updated, encoding="utf-8")
        except OSError as exc:
            yield ErrorOutput(message=f"cannot edit {raw}: {exc}")
            return
        self._snapshot(key, data)  # prior bytes, for undo (spec 054)
        self._reads[key] = _digest(updated.encode("utf-8"))
        yield TextBlock(text=f"edited {raw}: replaced 1 occurrence")

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

    async def _glob_files(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        pattern = str(call_input["pattern"])
        raw = str(call_input.get("path", "."))
        try:
            base = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        if not base.is_dir():
            yield ErrorOutput(message=f"not a directory: {raw}")
            return
        scope = context.working_scope.resolve()
        matches: list[str] = []
        try:
            for path in sorted(base.glob(pattern)):
                if len(matches) >= _SEARCH_MATCH_LIMIT:
                    break
                if not path.is_file():
                    continue
                try:
                    relative = path.resolve().relative_to(scope).as_posix()
                except ValueError:
                    continue
                matches.append(relative)
        except (ValueError, NotImplementedError) as exc:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"invalid glob pattern {pattern!r}: {exc}",
            )
            return
        if matches:
            yield TextBlock(text="\n".join(matches))
        else:
            yield TextBlock(text=f"no files match {pattern!r}")

    async def _grep(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        raw_pattern = str(call_input["pattern"])
        raw = str(call_input.get("path", "."))
        mode = str(call_input.get("output_mode", "content"))
        if mode not in ("content", "files_with_matches", "count"):
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"invalid output_mode {mode!r}; expected content, "
                    f"files_with_matches, or count"
                ),
            )
            return
        try:
            regex = re.compile(raw_pattern)
        except re.error as exc:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"invalid regular expression {raw_pattern!r}: {exc}",
            )
            return
        try:
            root = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        if not root.is_dir():
            yield ErrorOutput(message=f"not a directory: {raw}")
            return
        scope = context.working_scope.resolve()
        content_lines: list[str] = []
        file_matches: list[str] = []
        counts: list[str] = []
        capped = False
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.resolve().relative_to(scope).as_posix()
            per_file = 0
            for line_number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    per_file += 1
                    if mode == "content":
                        content_lines.append(
                            f"{relative}:{line_number}: {line.strip()}"
                        )
                        if len(content_lines) >= _SEARCH_MATCH_LIMIT:
                            capped = True
                            break
            if per_file:
                if mode == "files_with_matches":
                    file_matches.append(relative)
                elif mode == "count":
                    counts.append(f"{relative}: {per_file}")
            if capped or (
                mode != "content"
                and max(len(file_matches), len(counts)) >= _SEARCH_MATCH_LIMIT
            ):
                break
        if mode == "files_with_matches":
            results, empty = file_matches, f"no files match {raw_pattern!r}"
        elif mode == "count":
            results, empty = counts, f"no matches for {raw_pattern!r}"
        else:
            results, empty = content_lines, f"no matches for {raw_pattern!r}"
        yield TextBlock(text="\n".join(results) if results else empty)

    async def _run_command(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        command = str(call_input["command"])
        try:
            result = await self._executor.run(command, cwd=context.working_scope)
        except OSError as exc:
            yield ErrorOutput(message=f"cannot run command: {exc}")
            return
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        if stdout.strip():
            yield TextBlock(text=stdout)
        if result.returncode != 0:
            yield ErrorOutput(
                message=(
                    f"command failed with exit code {result.returncode}: "
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

    async def _exit_plan_mode(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """Submit a plan for a human approve/reject decision (spec 038, FR-005-FR-007).

        Reuses the existing human round-trip (``context.interactions.ask_question`` —
        the same broker ``ask_user`` uses), so it inherits the no-reviewer / disconnect
        semantics and emits the existing question/answer events (no new approval path,
        no event-schema change). On approve it clears the per-run plan-mode holder so
        subsequent non-read-only tools are allowed; on reject or no human it leaves
        plan mode active and returns a clear normalized outcome.
        """
        plan = str(call_input["plan"])
        broker = context.interactions
        if broker is None:
            yield ErrorOutput(message="no user is available to approve the plan")
            return
        question = Question(
            text=f"Approve this plan?\n\n{plan}", options=["approve", "reject"]
        )
        answers = await broker.ask_question([question])
        if answers is None:
            # No reviewer attached, or the question was cancelled (e.g. disconnect):
            # stay in plan mode, mirroring ask_user's no-user outcome.
            yield ErrorOutput(message="no user is available to approve the plan")
            return
        if answers and answers[0].strip().lower() == "approve":
            if context.plan_mode is not None:
                context.plan_mode.active = False
            yield TextBlock(text="plan approved; proceeding to execute")
            return
        yield TextBlock(text="plan not approved; remaining in plan mode")

    async def _todo_write(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """Record the run's todo list (spec 044). Set-the-whole-list: each call
        replaces the session's list with the validated submission; an empty list
        clears it. Validation is side-effect-free — on any invalid input the prior
        list is left unchanged. The list is per-session state, mirroring
        ``self._reads``; it touches neither the event schema nor the content model.
        """
        raw = call_input["todos"]
        if not isinstance(raw, list):
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION, message="todos must be a list"
            )
            return
        if len(raw) > _MAX_TODO_ITEMS:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"too many todos: {len(raw)} exceeds the maximum of "
                    f"{_MAX_TODO_ITEMS}"
                ),
            )
            return
        validated: list[dict[str, str]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"todo {index} must be an object",
                )
                return
            content = item.get("content")
            status = item.get("status")
            if not isinstance(content, str) or not content.strip():
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"todo {index} requires a non-empty 'content' string",
                )
                return
            if not isinstance(status, str) or status not in _TODO_STATUSES:
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=(
                        f"todo {index} has invalid status {status!r}; expected "
                        f"one of {', '.join(_TODO_STATUSES)}"
                    ),
                )
                return
            validated.append({"content": content, "status": status})
        self._todos[context.session_id] = validated
        if not validated:
            yield TextBlock(text="todo list cleared")
            return
        lines = [f"[{item['status']}] {item['content']}" for item in validated]
        yield TextBlock(text=f"Recorded {len(validated)} todos:\n" + "\n".join(lines))

    async def _notebook_edit(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """Edit a single Jupyter (.ipynb) cell (spec 046). Confined to the working
        scope (``_resolve``) and gated by the same stale-write guard as ``edit_file``
        (the notebook must have been read this session and be unchanged). The parsed
        document is round-tripped so all non-targeted cells / outputs / metadata and the
        top-level ``nbformat`` are preserved; any failure leaves the file unchanged.
        """
        raw = str(call_input["path"])
        mode = str(call_input["mode"])
        index_value = call_input["index"]
        if not isinstance(index_value, int) or isinstance(index_value, bool):
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION, message="index must be an integer"
            )
            return
        index: int = index_value
        if index < 0:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION, message="index must be non-negative"
            )
            return
        try:
            target = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        try:
            data = target.read_bytes()
        except OSError as exc:
            yield ErrorOutput(message=f"cannot edit {raw}: {exc}")
            return
        key = (context.session_id, str(target))
        recorded = self._reads.get(key)
        if recorded is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"stale edit rejected: {raw} exists but was not read in "
                    f"this session"
                ),
            )
            return
        if _digest(data) != recorded:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    f"stale edit rejected: {raw} changed since it was last "
                    f"read in this session"
                ),
            )
            return
        try:
            document = json.loads(data.decode("utf-8", errors="replace"))
        except ValueError as exc:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"{raw} is not valid JSON: {exc}",
            )
            return
        if not isinstance(document, dict) or not isinstance(
            document.get("cells"), list
        ):
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"{raw} is not a valid notebook (no 'cells' list)",
            )
            return
        cells = document["cells"]
        last = len(cells) - 1
        if mode == "delete":
            if not 0 <= index < len(cells):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"cell index {index} out of range (0..{last})",
                )
                return
            del cells[index]
            summary = f"deleted cell {index}"
        elif mode == "replace":
            source = call_input.get("source")
            if not 0 <= index < len(cells):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"cell index {index} out of range (0..{last})",
                )
                return
            if not isinstance(source, str):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message="replace requires a 'source' string",
                )
                return
            cell = cells[index]
            if not isinstance(cell, dict):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"cell {index} is not an object",
                )
                return
            cell["source"] = source
            summary = f"replaced cell {index}"
        elif mode == "insert":
            source = call_input.get("source")
            cell_type = call_input.get("cell_type")
            if not 0 <= index <= len(cells):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message=f"insert index {index} out of range (0..{len(cells)})",
                )
                return
            if not isinstance(source, str):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message="insert requires a 'source' string",
                )
                return
            if cell_type not in ("code", "markdown"):
                yield ErrorOutput(
                    category=ErrorCategory.VALIDATION,
                    message="insert requires a 'cell_type' of 'code' or 'markdown'",
                )
                return
            new_cell: dict[str, object] = {
                "cell_type": cell_type,
                "source": source,
                "metadata": {},
            }
            if cell_type == "code":
                new_cell["outputs"] = []
                new_cell["execution_count"] = None
            cells.insert(index, new_cell)
            summary = f"inserted {cell_type} cell at {index}"
        else:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=f"invalid mode {mode!r}; expected replace, insert, or delete",
            )
            return
        serialized = json.dumps(document, indent=1, ensure_ascii=False) + "\n"
        try:
            target.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            yield ErrorOutput(message=f"cannot write {raw}: {exc}")
            return
        self._snapshot(key, data)  # prior bytes, for undo (spec 054)
        self._reads[key] = _digest(serialized.encode("utf-8"))
        yield TextBlock(text=f"{summary} in {raw}")

    async def _undo_file(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        """Restore a file to its most recent pre-edit snapshot (spec 054), within the
        working scope; re-syncs the stale-write guard so a later edit is accepted."""
        raw = str(call_input["path"])
        try:
            target = self._resolve(context, raw)
        except _PathOutsideScopeError as exc:
            yield ErrorOutput(category=ErrorCategory.VALIDATION, message=str(exc))
            return
        key = (context.session_id, str(target))
        prior: bytes | None = None
        for position in range(len(self._snapshots) - 1, -1, -1):
            if self._snapshots[position][0] == key:
                prior = self._snapshots.pop(position)[1]
                break
        if prior is None:
            yield TextBlock(text=f"nothing to undo for {raw}")
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(prior)
        except OSError as exc:
            yield ErrorOutput(message=f"cannot undo {raw}: {exc}")
            return
        self._reads[key] = _digest(prior)
        yield TextBlock(text=f"reverted {raw} to its previous version")
