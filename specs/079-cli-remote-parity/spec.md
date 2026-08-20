# Feature Specification: CLI and Remote Parity

**Feature Branch**: `079-cli-remote-parity`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "CLI/remote parity (roadmap unit 079): expand slash commands and interactive CLI affordances, then add a remote-control bridge with remote-safe command policy, permission callbacks, interrupt, and reconnect. The remote bridge is the terminal host acting as a client of the existing web/API host; the outward contract does not change. Vim, voice, and IDE-like UX parity are P3 follow-ups outside this unit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hold a Continuous Conversation in the Terminal (Priority: P1)

An operator opens an interactive conversation in their terminal, sends several messages in a row, and the agent carries everything said earlier in that conversation forward. When they finish, the conversation is a single addressable session they can list and pick up again later.

**Why this priority**: Today every turn typed at the terminal starts a brand-new conversation, so nothing carries over — the terminal is the only host surface without conversational memory. Every other affordance in this unit (answering an approval, interrupting a turn, driving a remote agent) assumes one live conversation to act on, so this story is the foundation the rest stand on.

**Independent Test**: Start an interactive conversation, state a fact in the first message, refer back to it in the second, and confirm the reply reflects the earlier turn; leave, list conversations, and pick the same one up again.

**Acceptance Scenarios**:

1. **Given** an open interactive conversation, **When** the operator sends two messages in sequence, **Then** the second turn carries the first turn's context and both turns belong to the same conversation identity.
2. **Given** an open interactive conversation, **When** the operator ends it by an exit instruction or by closing input, **Then** the conversation closes cleanly and leaves nothing waiting on an answer.
3. **Given** durable storage is configured and a previous conversation exists, **When** the operator picks that conversation up interactively, **Then** its earlier context is available and further turns continue the same conversation.
4. **Given** durable storage is not configured, **When** the operator asks to pick up a previous conversation, **Then** they receive a public-safe explanation and the terminal stays usable.

---

### User Story 2 - Answer Approvals and Questions in the Terminal (Priority: P1)

While a turn is running, the agent asks permission to use a tool, or asks the operator a question. The operator sees the request in the terminal, answers it there, and the turn continues — without switching to another host surface.

**Why this priority**: Without this, any conversation that reaches a gated tool simply stalls at the terminal. It is the difference between a terminal that can demo an agent and one that can supervise it, and it is a prerequisite for the same capability over a remote connection (US6).

**Independent Test**: Run a turn that requests a gated tool, observe the request rendered in the terminal, answer it both ways (allow and deny) and at both scopes (this request only, and the rest of the conversation), and confirm the turn proceeds accordingly; separately, answer an agent question and confirm the answer reaches the turn.

**Acceptance Scenarios**:

1. **Given** a running turn requests permission for a tool, **When** the request reaches the terminal, **Then** the operator sees a public-safe summary sufficient to decide — the tool's identity and the scope of the request — and never raw tool input or output.
2. **Given** a pending permission request, **When** the operator allows or denies it for this request only, **Then** that decision applies to this request and the next equivalent request asks again.
3. **Given** a pending permission request, **When** the operator allows or denies it for the rest of the conversation, **Then** equivalent later requests in the same conversation follow that decision without asking again.
4. **Given** a running turn asks the operator a question, **When** the operator answers in the terminal, **Then** the answer reaches the turn and the turn continues.
5. **Given** a permission request or question is pending, **When** the operator ends the conversation or interrupts, **Then** every pending request resolves — permissions deny, questions cancel — and nothing is left waiting.
6. **Given** any request is rendered, **When** the terminal displays it, **Then** no credential, private path, or raw exception appears.

---

### User Story 3 - Interrupt a Turn That Is Already Running (Priority: P1)

An operator watching a turn go the wrong way stops it mid-flight and lands back at the prompt with the conversation intact, instead of having to wait it out or kill the whole terminal host.

**Why this priority**: Interruption is the operator's only real-time control over a running agent. Today interruption is possible only while idle at the prompt, so a long or wrong turn cannot be stopped without discarding the whole conversation.

**Independent Test**: Start a turn that produces output over time, interrupt it mid-stream, confirm the prompt returns, confirm the conversation is still usable for the next turn, and confirm interrupting at an idle prompt still ends the interactive conversation as it does today.

**Acceptance Scenarios**:

1. **Given** a turn is running, **When** the operator interrupts, **Then** the turn stops and the operator returns to the prompt with the same conversation still open.
2. **Given** a turn has been interrupted, **When** the operator sends the next message, **Then** it continues the same conversation.
3. **Given** an interrupt is requested, **When** it arrives before the turn's work begins or while output is streaming, **Then** it takes effect in both cases.
4. **Given** a turn is interrupted, **When** the terminal reports the result, **Then** the operator sees a public-safe termination explanation rather than a stack trace or a silent stop.
5. **Given** the operator is idle at the prompt, **When** they interrupt, **Then** the interactive conversation ends cleanly, preserving today's behavior.
6. **Given** a permission request is pending, **When** the operator interrupts instead of answering, **Then** the pending request resolves as a denial and nothing hangs.

---

### User Story 4 - More Built-in Commands, Identical on Every Surface (Priority: P2)

An operator uses a small set of additional built-in commands — listing what commands exist, listing and picking up conversations, clearing the current view, inspecting the current permission posture — and gets the same answer whether they typed it in the terminal, sent it from the web application, or typed it in the desktop composer.

**Why this priority**: The existing command surface answers only four commands, and the terminal has no way to discover even those. These are navigational affordances that make the other stories usable, but none of them blocks supervising an agent, so they rank below P1.

**Independent Test**: Invoke each new command from the terminal and from the web/API host, compare the results, and confirm identical semantics; confirm an unknown command is refused without disrupting the conversation.

**Acceptance Scenarios**:

1. **Given** the shared command surface, **When** a new built-in command is invoked from the terminal, from the web/API host, or from the desktop composer, **Then** all three produce the same public-safe result from one shared definition.
2. **Given** any command, **When** its handler fails for any reason, **Then** dispatch still returns a public-safe result and never raises, never reaches the tool gateway, and never emits a runtime event.
3. **Given** the operator does not know what is available, **When** they invoke the listing command, **Then** they see the commands available to them with a one-line description each.
4. **Given** an unrecognized command, **When** it is invoked, **Then** the operator receives a public-safe "unknown command" result and the conversation continues unaffected.
5. **Given** a command needs a conversation and none is open, **When** it is invoked, **Then** the result explains that in public-safe terms rather than failing.

---

### User Story 5 - Know Which Commands Are Safe to Run Remotely (Priority: P2)

Every command declares whether it is safe to run over a remote connection, and the listing an operator sees reflects what is actually usable where they are. A command that must not run remotely is refused there, clearly and without leaking why in host-private terms.

**Why this priority**: The remote bridge (US6) needs a decision rule for every command, and inventing that rule inside the remote path would fork command semantics across surfaces. Classifying at the command surface keeps one answer for all hosts — but it delivers no operator value until the remote bridge exists, so it ranks with US4 rather than P1.

**Independent Test**: Confirm every command carries a classification; invoke a remote-safe and a non-remote-safe command from a remote context and from a local context; confirm the listing differs appropriately and the existing four commands behave exactly as they do today.

**Acceptance Scenarios**:

1. **Given** the command surface, **When** commands are enumerated, **Then** every command carries an explicit remote-safety classification.
2. **Given** a command classified as not remote-safe, **When** it is invoked from a remote context, **Then** it is refused with a public-safe explanation and no host-private detail.
3. **Given** a command classified as remote-safe, **When** it is invoked from a remote context, **Then** it behaves as it does locally.
4. **Given** the listing command, **When** it runs in a local context and in a remote context, **Then** each listing shows the commands usable in that context.
5. **Given** the four commands that already exist, **When** they are invoked on the surfaces that already consume them, **Then** their behavior is unchanged by the introduction of classification.

---

### User Story 6 - Drive a Remote Agent from the Terminal (Priority: P3)

An operator points their terminal at a LoopPlane server they have access to, opens a conversation there or attaches to one of their own that is already running, watches it stream, answers its approvals and questions, and interrupts it — all from the terminal, with only remote-safe commands available.

**Why this priority**: This is the parity goal the unit is named for, and it is the largest single piece of work. It depends on US1–US3 (there must be a local interaction model to project remotely) and on US5 (there must be a command policy), so it is sequenced last among the value-delivering stories.

**Independent Test**: Against a reachable server, connect with a credential from the environment, open a conversation, send a turn, answer one approval, interrupt a turn, list conversations, and disconnect — then repeat the attach path against a conversation opened earlier.

**Acceptance Scenarios**:

1. **Given** a server address and a credential source, **When** the operator starts a remote conversation, **Then** the terminal connects and the operator can send turns and watch them stream with the same public-safe rendering used locally.
2. **Given** a remote conversation the operator owns, **When** they attach to it by its identifier, **Then** they join it and can act on it.
3. **Given** a remote turn requests permission or asks a question, **When** the operator answers in the terminal, **Then** the answer reaches the remote turn and it continues.
4. **Given** a remote turn is running, **When** the operator interrupts, **Then** the remote turn stops, the terminal states that interruption ended the live remote connection, the operator returns to the prompt, and the conversation remains listed with its history available.
5. **Given** a credential is missing, malformed, or rejected, **When** the operator attempts to connect, **Then** they receive a public-safe failure that never echoes the credential or any part of it.
6. **Given** a conversation identifier that belongs to another principal or does not exist, **When** the operator attaches to it, **Then** the outcome does not disclose which of the two is the case.
7. **Given** the remote capability is not used, **When** the operator runs the terminal host as before, **Then** its behavior is unchanged and it still works with no credential and no optional capability installed.
8. **Given** the optional network capability is unavailable in the environment, **When** the operator attempts a remote connection, **Then** they receive a public-safe explanation of what is missing rather than a raw failure.

---

### User Story 7 - Survive a Dropped Connection (Priority: P3)

An operator's remote stream drops — the network blips, a laptop sleeps — and the terminal reconnects on its own and picks up exactly where it left off, with nothing repeated and nothing missed.

**Why this priority**: A remote control surface that loses the thread on every network blip is not trustworthy for supervising real work. It is separable from US6 (a remote connection is useful before it is resilient) and therefore specified as its own story.

**Independent Test**: Establish a remote conversation, force the stream to drop mid-turn, and verify the terminal reconnects, that the event sequence the operator sees contains no gap and no duplicate across the break, and that a conversation which ended during the break is reported cleanly.

**Acceptance Scenarios**:

1. **Given** an active remote stream, **When** the connection drops while a turn is in progress, **Then** the terminal reconnects without operator action and resumes from the last position it received.
2. **Given** a reconnection has completed, **When** the operator reviews what they saw, **Then** the sequence contains neither a duplicated nor a missing event across the break.
3. **Given** a reconnection is in progress, **When** the operator is waiting, **Then** they can see that the terminal is reconnecting rather than silently hung.
4. **Given** the conversation ended or is no longer resumable while the connection was down, **When** reconnection is attempted, **Then** the operator receives a public-safe explanation and the terminal exits that conversation cleanly.
5. **Given** reconnection keeps failing, **When** a bounded number of attempts has been exhausted, **Then** the terminal stops retrying, says so in public-safe terms, and returns control to the operator.

---

### Edge Cases

- The operator supplies no credential, an empty credential, a malformed credential, or one the server rejects — each fails without echoing any part of the value.
- The optional network capability is not installed in the environment: remote features explain what is missing; every non-remote feature keeps working.
- The server is unreachable, refuses the connection, or responds too slowly: the operator gets a bounded, public-safe failure rather than an indefinite hang.
- A conversation identifier belongs to another principal, or does not exist: both cases produce the same non-disclosing outcome.
- Reconnection targets a conversation that has already ended or whose replayable history is no longer available.
- The operator interrupts while a permission request is pending, or while a reconnection is in progress.
- A non-remote-safe command is invoked from a remote context; an unknown command is invoked from either context.
- The operator interrupts twice in quick succession, or interrupts at the idle prompt (which must keep today's meaning: end the interactive conversation).
- A command that needs an open conversation is invoked before one exists.
- Durable storage is not configured but the operator asks to list or pick up previous conversations.

## Requirements *(mandatory)*

### Functional Requirements

**Continuous interactive conversation (US1)**

- **FR-001**: The terminal host MUST conduct all turns of one interactive conversation within a single conversation identity until the operator ends it or starts another.
- **FR-002**: The terminal host MUST release the conversation cleanly when interactive input ends, leaving no pending request unresolved.
- **FR-003**: Operators MUST be able to pick up a previously stored conversation interactively and continue it with its earlier context available.
- **FR-004**: When durable storage is not configured, requests to list or pick up previous conversations MUST return a public-safe explanation instead of failing.

**Approvals and questions (US2)**

- **FR-005**: When a running turn requests permission for a tool, the terminal host MUST present a public-safe summary sufficient to decide, and MUST NOT present raw tool input or output.
- **FR-006**: Operators MUST be able to allow or deny a permission request, and MUST be able to choose whether the decision applies to that request alone or to the remainder of the conversation.
- **FR-007**: Operators MUST be able to answer a question asked by a running turn.
- **FR-008**: When an operator ends the conversation or interrupts, the system MUST resolve every pending request — permission requests as denials, questions as cancellations — so no turn is left waiting.
- **FR-009**: Terminal output MUST NOT contain credentials, private filesystem paths, internal identifiers, or raw exception text.

**Interruption (US3)**

- **FR-010**: Operators MUST be able to interrupt a turn that is already running and return to the prompt with the conversation still open and usable.
- **FR-011**: An interrupt MUST take effect both before a turn's work begins and while its output is streaming.
- **FR-012**: After an interrupt, the terminal host MUST report a public-safe termination outcome.
- **FR-013**: Interrupting while idle at the prompt MUST continue to end the interactive conversation, preserving existing behavior.

**Command surface (US4)**

- **FR-014**: The shared command surface MUST gain a small set of additional built-in commands whose semantics are identical on the terminal host, the web/API host, and the desktop composer, from one shared definition.
- **FR-015**: Command dispatch MUST remain fail-safe: it MUST NOT raise, MUST NOT reach the tool gateway, MUST NOT emit runtime events, and MUST always return a public-safe result.
- **FR-016**: The command surface MUST provide a command that lists the commands available to the operator with a one-line description of each.
- **FR-017**: An unrecognized command MUST produce a public-safe "unknown command" result without disrupting the conversation.
- **FR-018**: A command that requires an open conversation MUST explain its unavailability in public-safe terms when none is open.

**Remote-safety classification (US5)**

- **FR-019**: Every command MUST carry an explicit remote-safety classification.
- **FR-020**: Introducing the classification MUST leave the behavior of the four existing commands unchanged on the surfaces that already consume them.
- **FR-021**: A command that is not remote-safe MUST be refused when invoked from a remote context, with a public-safe explanation that discloses no host-private detail.
- **FR-022**: The listing command MUST reflect the commands usable in the operator's current context.

**Remote operation (US6)**

- **FR-023**: Operators MUST be able to direct the terminal host at a LoopPlane server by supplying a server address and a credential source.
- **FR-024**: Credentials MUST be read only from the environment or an explicit argument, and MUST NOT appear in any output, rendering, diagnostic, or error message.
- **FR-025**: Operators MUST be able to open a new remote conversation or attach to an existing conversation they own.
- **FR-026**: Remote turns MUST be rendered with the same public-safe rules as local turns.
- **FR-027**: Operators MUST be able to answer remote permission requests and remote questions from the terminal.
- **FR-028**: Operators MUST be able to interrupt a running remote turn. The terminal MUST report that interruption ends the live remote connection, MUST return the operator to the prompt, and the conversation MUST remain listed with its history available afterwards. (Local interruption keeps the conversation open; the remote case differs because ending the live connection is the server's existing, unchanged behavior — see Assumptions.)
- **FR-029**: Attaching to a conversation identifier that the operator does not own MUST NOT disclose whether that conversation exists.
- **FR-030**: The remote capability MUST be additive: with it unused, the terminal host's existing behavior is unchanged and it remains usable with no credential and no optional capability installed.
- **FR-031**: When the optional network capability required for remote operation is unavailable, the terminal host MUST explain what is missing in public-safe terms instead of surfacing a raw failure.
- **FR-032**: A server that is unreachable, refusing, or unresponsive MUST produce a bounded, public-safe failure rather than an indefinite wait. Connecting is bounded; **reading a turn is not** — a turn takes as long as the model takes, and a read deadline would end the conversation and misreport it as a network failure.

**Reconnection (US7)**

- **FR-033**: When a remote stream drops, the terminal host MUST attempt to reconnect without operator action and resume from the last position it received.
- **FR-034**: Across a reconnection, the sequence of events the operator observes MUST contain no duplicate and no gap.
- **FR-035**: While reconnecting, the terminal host MUST make that state visible to the operator rather than appearing hung.
- **FR-036**: When the conversation ended or is no longer resumable, reconnection MUST report that in public-safe terms and close that conversation cleanly.
- **FR-037**: Reconnection attempts MUST be bounded **and spaced**; on exhaustion the terminal host MUST stop retrying, say so, and return control to the operator. Retrying without a wait burns every attempt in milliseconds — too fast to outlast even a brief server restart — and starves everything else the terminal is doing.

**Ownership of session-scoped commands (added after review)**

- **FR-041**: A command that reads one conversation MUST declare itself session-scoped, and every host that has principals MUST check ownership before dispatching it. The check MUST be driven by that declaration rather than by a list the host maintains separately, so adding a command cannot silently skip it.
- **FR-042**: A session-scoped command handler MUST additionally refuse a conversation the caller does not own, so a host that omits its own check degrades to "not found" rather than disclosing. A conversation that is not the caller's and one that does not exist MUST be indistinguishable.

**Interruption that a real terminal produces (revised after review)**

- **FR-043**: Interruption MUST be handled through a mechanism that a real terminal's Ctrl-C actually triggers. Relying on an exception propagating out of the turn is insufficient: under the terminal host's event-loop runner a real interrupt cancels the task instead, so such a handler never runs outside tests.

**Boundaries (all stories)**

- **FR-038**: The terminal host MUST NOT execute any tool itself; it MUST consume only the normalized event stream.
- **FR-039**: Commands MUST remain host presentation, never becoming tools and never bypassing the tool gateway or the event bus.
- **FR-040**: This unit MUST NOT change the outward web contract, any event or record schema, or any existing default value.

### Key Entities

- **Interactive conversation**: the single, continuing exchange an operator conducts in the terminal — the thing turns belong to, approvals are scoped to, interrupts act on, and stored conversations are picked up as.
- **Command descriptor**: what an operator can be told about one command — its name, a one-line description, and its remote-safety classification.
- **Remote connection profile**: what the terminal host needs to reach a server — the server address, the credential source, and the conversation being opened or attached to. Holds no credential value beyond the life of the connection.
- **Stream position**: the operator's place in a remote conversation's event sequence, used to resume after a break without repeating or skipping.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an interactive conversation of at least three turns, 100% of turns belong to the same conversation, and a later turn can correctly refer to something stated in an earlier one.
- **SC-002**: An operator can complete a full supervised task — send a turn, answer one permission request, answer one question, and finish — entirely within the terminal, without switching to another host surface.
- **SC-003**: An operator can stop a running turn and be back at a usable prompt within 1 second of interrupting, with the conversation still open.
- **SC-004**: After any interrupt or exit, zero permission requests and zero questions remain unresolved.
- **SC-005**: Each newly added command returns the same result on all three surfaces that share the command surface.
- **SC-006**: Every command reports a remote-safety classification, and 100% of non-remote-safe commands are refused when invoked remotely.
- **SC-007**: An operator can complete a remote work cycle — connect, open or attach, send a turn, answer one approval, interrupt, disconnect — from the terminal alone.
- **SC-008**: After one forced connection break mid-turn, the reconnected stream shows zero duplicated and zero missing events.
- **SC-009**: With no credential configured and no optional capability installed, every command the terminal host supported before this unit behaves exactly as it did before.
- **SC-010**: Across every scenario above, no terminal output contains a credential, a private filesystem path, or raw exception text, as verified by the project's public-safety check.

## Assumptions

- The remote server is an existing LoopPlane web/API host; this unit adds a client for it and changes nothing the server exposes.
- The operator already has a credential for that server, obtained outside this unit; the terminal host never mints, stores, or renews one.
- Changing the interactive conversation from "a new conversation per turn" to "one continuing conversation" is a deliberate, user-visible behavior change, accepted as the point of User Story 1.
- The terminal host remains credential-free by default and continues to work with no network access; remote operation is opt-in per invocation.
- Remote operation requires an optional capability that may not be installed in every environment; its absence is a supported, explained state rather than a defect.
- "Remote-safe" is a per-command property decided once at the shared command surface, not re-derived by each host.
- The priorities P1/P2/P3 above rank stories inside this unit. They are unrelated to the roadmap's "P3 follow-up" label for Vim, voice, and IDE-like parity, which is out of scope entirely (see below).
- **Local and remote interruption differ, deliberately.** Interrupting locally leaves the conversation open for the next turn. Interrupting remotely ends the live connection, because that is what the server's existing interrupt does — it is not something this unit changes, since altering it would be an outward-contract change. The conversation itself survives either way: it stays listed, and its history stays available.
- **Reconnection's no-loss guarantee belongs to the server, and depends on its configuration.** FR-034 holds when the server retains replayable events; a server configured without that retention emits no event identifiers, so there is nothing for a reconnect to resume from and anything missed while disconnected is genuinely lost. The terminal cannot negotiate this, but it can see it — so when it reconnects without an identifier it says so plainly rather than implying a resume that cannot happen.
- **Terminology.** This specification says *conversation* for what the implementation and the server's interface call a *session*. They are the same thing; the user-facing word is used here because the specification is written for readers who do not work in the codebase.

## Dependencies

- Unit 017 (terminal host) provides the command structure, rendering, and provider selection this unit extends. Its "no multi-user or remote operation" exclusion is deliberately reversed here.
- Unit 065 (backend-semantic commands) provides the shared, fail-safe command surface this unit extends with new commands and a classification.
- Units 074–078 provide the web/API host session, streaming, reconnection, approval, and cancellation behavior that the remote client consumes unchanged.

## Out of Scope

- Vim-style editing, voice input, and IDE-like editor affordances — roadmap follow-ups that require separate authorization.
- User-defined commands and any command plugin or discovery system; the command set remains built-in, as unit 065 established.
- Switching models mid-conversation; the existing read-only model command is unchanged.
- A full-screen terminal user interface.
- Any new, changed, or removed outward web endpoint, field, or streaming contract.
- Any new transport, protocol, or separate remote package.
- Any new dependency or optional capability beyond those the project already declares.
- Server-side changes of any kind, including new server-side command policy enforcement; classification is a property of the shared command surface consumed by hosts.
