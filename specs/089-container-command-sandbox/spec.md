# Feature Specification: Container Command Sandbox

**Feature Branch**: `089-container-command-sandbox`
**Created**: 2026-10-08
**Status**: Draft
**Input**: Maintainer selected the remaining G11 container sandbox and approved one new optional extra plus one new ADR. The default command path stays unchanged. No event or checkpoint change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a command inside a container (Priority: P1)

An operator who exposes command execution wants that command to run in a container
instead of on the host. The container has no network, does not inherit the host
environment, and cannot gain extra privileges. The operator names the image.
The runtime does not download an image.

**Why this priority**: This is the remaining G11 slice. The POSIX jail does not
serve a host that cannot apply those limits.
**Independent Test**: Inject the container executor with a stand-in runtime and
one named image. The recorded launch has no network, a read-only root, no added
capabilities, and only the working directory mounted.

**Acceptance Scenarios**:

1. **Given** an operator selects the container executor and a local image,
   **when** a command runs, **then** it runs in that image with no network, a
   read-only root filesystem, every capability dropped, and no host environment.
2. **Given** the command finishes, **when** its output is returned, **then** the
   caller sees the same success and failure shapes as an ordinary command.
3. **Given** the command runs past its time limit, **when** the limit is reached,
   **then** the command is stopped and the result says it was terminated.

### User Story 2 - Leave unconfigured command execution unchanged (Priority: P1)

A deployment that never selects the container executor keeps today's host command
execution, including on Windows.

**Why this priority**: The sandbox is opt-in. Selecting nothing must stay byte-identical.
**Independent Test**: Build the default tool adapter and run one benign command.

**Acceptance Scenarios**:

1. **Given** no container executor is selected, **when** a command runs,
   **then** it uses the existing host executor.
2. **Given** the POSIX jail is requested on a platform that cannot provide it,
   **when** it is constructed, **then** it still refuses. The container executor
   does not become a silent fallback.

### User Story 3 - Fail closed without a usable runtime (Priority: P2)

The container executor is usable only when its optional package and a local
daemon are present, and only for an image that is already local. A failure
does not describe sockets, image names, or exception text.

**Why this priority**: A missing sandbox must not turn into an unconfined command.
**Independent Test**: Construct the executor with the package hidden, with a
daemon that fails, and with an image name that is not usable.

**Acceptance Scenarios**:

1. **Given** the optional package is not installed, **when** the executor is
   constructed without a stand-in runtime, **then** construction fails and no
   command starts.
2. **Given** the daemon cannot be reached, or the image is not local, **when**
   the executor is constructed, **then** construction fails with a fixed message
   that does not repeat the runtime's own text.
3. **Given** an image name is empty, starts with a dash, or contains a path
   traversal or a scheme, **when** the executor is constructed, **then** it
   refuses before any runtime call.

### Edge Cases

- A second volume, a privileged flag, or a network mode cannot be passed through
  the executor. Those controls are not parameters.
- Removing the container after the command is best-effort. A removal failure
  does not replace the command's result.
- The working directory is mounted read-write at one fixed location inside the
  container. The rest of the host filesystem is not mounted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The default command executor remains the host executor.
- **FR-002**: An operator can select a container executor by passing it into the
  existing command-executor seam, together with an image name.
- **FR-003**: A container command has no network, a read-only root, all
  capabilities dropped, privilege escalation disabled, an empty environment,
  and a non-root user.
- **FR-004**: The only host directory mounted into the container is the command's
  working directory.
- **FR-005**: The runtime does not pull or build an image.
- **FR-006**: Memory, process count, CPU time, file size, and wall-clock limits
  match the limits already used by the POSIX jail unless the caller supplies
  the same limit object.
- **FR-007**: A wall-clock expiry stops the container and returns a terminated
  result. It does not leave the command running.
- **FR-008**: Construction without the optional package, without a reachable
  daemon, or without a local image fails before a command starts.
- **FR-009**: Failure text is a fixed sentence. It does not include runtime
  exception text, socket paths, or the image name.
- **FR-010**: The executor's visible representation does not include the image
  or the daemon address.
- **FR-011**: No event, checkpoint field, termination reason, HTTP route, or
  default command path is added.

### Key Entities

- **Container executor**: the opt-in command runner bound to one image.
- **Launch**: the image, the command, the working directory, and the resource
  limits. Confinement flags are not part of the caller's input.
- **Command result**: the exit code and the two output streams already returned
  for a host command.

## Success Criteria *(mandatory)*

- **SC-001**: A stand-in runtime records one launch whose confinement matches
  FR-003 and FR-004, and the tool adapter returns that command's output.
- **SC-002**: A launch that exceeds its wall clock is killed, removed, and
  reported as terminated.
- **SC-003**: An unusable image name, a missing package, and an unreachable
  daemon each fail construction without echoing the runtime's text.
- **SC-004**: The default adapter's executor is still the host executor.

## Assumptions

- The maintainer approved one optional extra and one ADR on 2026-10-08.
- The container includes a shell at `sh`. An image without it fails as a
  command failure, not as a host fallback.
- The local daemon and the named image are the operator's responsibility.
  This unit does not install either.
- Tests use a stand-in runtime. They do not start a daemon.
- Network-namespace work beyond "no network", syscall filters, and sandboxing
  tools other than command execution stay deferred.

## Out of Scope

- Changing the default executor or the POSIX jail's Windows refusal.
- Pulling images, publishing images, or accepting a registry credential.
- A new HTTP field, configuration default, event, checkpoint field, or
  termination reason.
- Sandboxing tools other than command execution.
- Live run migration.
