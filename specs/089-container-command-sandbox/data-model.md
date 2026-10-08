# Data Model: Container Command Sandbox

## Container executor

- One image name, validated before a runtime call.
- Optional resource limits. When omitted, the POSIX jail defaults apply.
- An engine. Tests inject one. Production constructs it from the local daemon.
- No persisted record. The executor holds no command history.

## Launch

- Image, shell command, one `ResourceLimits` value, and the host working-directory path.
- Confinement is not stored on the launch. One function turns that launch into the
  SDK call, including ulimit objects. It does not build a second dictionary and
  parse it back.

## Command result

- Unchanged: exit code, stdout bytes, stderr bytes.
- Wall-clock expiry uses exit code 124 and appends the existing terminated sentence.

## States

- Usable: package present, daemon answered, image present locally.
- Refused: any of those checks failed, or the image name is not a single token.
- There is no degraded or host-fallback state.
