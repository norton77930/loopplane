# Phase 1 Data Model: Web Agent Inspection Panels

Additive, metadata-only view types. No persistent model change; no runtime type change.

## Host inspection dataclasses (`loopplane/host/inspect.py`, frozen)

```python
@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    autonomous: bool          # profile.autonomous_invocation == "allowed"
    approval_required: bool
    source: str               # the source directory label
    # NOTE: `instructions` is deliberately excluded (may carry substituted secrets).

@dataclass(frozen=True)
class ToolInfo:
    name: str
    description: str
    read_only: bool
    source: str               # "internal" | "external-server:{name}" | ...

@dataclass(frozen=True)
class McpServerInfo:
    name: str                 # the {name} from source "external-server:{name}"
    tools: tuple[str, ...]    # the qualified tool names that server exposes

@dataclass(frozen=True)
class MemoryEntryInfo:
    type: str                 # "user" | "project" | "reference" | "feedback" | ...
    name: str
    description: str
    snippet: str              # bounded prefix of `body` (full body is not exposed)
```

### Pure projection helpers (`inspect.py`)

| Helper | Input | Output |
|---|---|---|
| `skills_view(skills)` | `Mapping[str, LoadedSkill]` | `tuple[SkillInfo, ...]` (sorted by name) |
| `tools_view(descriptors)` | `Sequence[ToolDescriptor]` | `tuple[ToolInfo, ...]` (sorted by name) |
| `mcp_view(descriptors)` | `Sequence[ToolDescriptor]` | `tuple[McpServerInfo, ...]` (group `external-server:*` by name) |
| `memory_view(entries, query, limit)` | `Sequence[MemoryEntry], str \| None, int` | `tuple[MemoryEntryInfo, ...]` (filtered via `select_entries` when query) |

`SNIPPET_LIMIT` (e.g. 200 chars) bounds the memory snippet. All helpers are pure (no I/O, no
mutation) and exclude every risky field.

## Host query methods (`LoopPlaneHost`)

```python
def inspect_skills(self) -> tuple[SkillInfo, ...]       # skills_view(self._assembled.skills)
def inspect_tools(self) -> tuple[ToolInfo, ...]         # tools_view(self._assembled.gateway.descriptors())
def inspect_mcp(self) -> tuple[McpServerInfo, ...]      # mcp_view(self._assembled.gateway.descriptors())
def inspect_memory(self, query: str | None = None) -> tuple[MemoryEntryInfo, ...]
    # memory_view(self._assembled.memory_store.list_entries(), query) or () when memory_store is None
```

`host.skill_problems` (already present) supplies the skills panel's load problems.

## AssembledRuntime (additive fields)

```python
@dataclass
class AssembledRuntime:
    controller: RuntimeController
    sink: RunSink
    artifact_store: ArtifactStore | None
    checkpoint_store: CheckpointStore | None
    skill_problems: tuple[str, ...]
    gateway: ToolGateway              # NEW (already built in assemble)
    skills: Mapping[str, LoadedSkill] # NEW (skills_map or {})
    memory_store: MemoryStore | None  # NEW (already built in assemble)
```

## webapi view models (`loopplane/webapi/models.py`, Pydantic, metadata-only)

```python
class SkillView(BaseModel):       name: str; description: str; autonomous: bool; approval_required: bool; source: str
class SkillsResponse(BaseModel):  skills: list[SkillView]; problems: list[str]
class ToolView(BaseModel):        name: str; description: str; read_only: bool; source: str
class McpServerView(BaseModel):   name: str; tools: list[str]
class MemoryEntryView(BaseModel): type: str; name: str; description: str; snippet: str
```

Each has a `from_*` classmethod projecting the host dataclass (mirroring `SessionSummaryView`).

## Frontend types (`apps/web/src/api/types.ts`)

```ts
export interface SkillView { name: string; description: string; autonomous: boolean; approval_required: boolean; source: string; }
export interface SkillsResponse { skills: SkillView[]; problems: string[]; }
export interface ToolView { name: string; description: string; read_only: boolean; source: string; }
export interface McpServerView { name: string; tools: string[]; }
export interface MemoryEntryView { type: string; name: string; description: string; snippet: string; }
```
