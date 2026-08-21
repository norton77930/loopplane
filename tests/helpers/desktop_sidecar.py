"""In-memory stdio / clock / fault harness for Desktop sidecar tests (T011)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class FakeClock:
    """Injectable monotonic clock (seconds)."""

    now: float = 0.0

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class ByteSplitStdio:
    """UTF-8 stdio that can deliver writes in arbitrary byte fragments."""

    _out: bytearray = field(default_factory=bytearray)
    _in: bytearray = field(default_factory=bytearray)
    read_chunk_size: int = 1
    fail_on_write: bool = False
    fail_on_read: bool = False

    def write(self, data: bytes | str) -> int:
        if self.fail_on_write:
            raise OSError("synthetic write failure")
        raw = data.encode("utf-8") if isinstance(data, str) else data
        self._out.extend(raw)
        return len(raw)

    def writelines(self, lines: list[bytes | str]) -> None:
        for line in lines:
            self.write(line)

    def feed_input(self, data: bytes | str) -> None:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        self._in.extend(raw)

    def read(self, n: int = -1) -> bytes:
        if self.fail_on_read:
            raise OSError("synthetic read failure")
        if n < 0:
            n = len(self._in)
        n = min(n, self.read_chunk_size, len(self._in))
        chunk = bytes(self._in[:n])
        del self._in[:n]
        return chunk

    def readline(self) -> bytes:
        if self.fail_on_read:
            raise OSError("synthetic read failure")
        if not self._in:
            return b""
        # Honor byte-split: may return partial line.
        idx = bytes(self._in).find(b"\n")
        if idx < 0:
            take = min(self.read_chunk_size, len(self._in))
        else:
            take = min(self.read_chunk_size, idx + 1)
        chunk = bytes(self._in[:take])
        del self._in[:take]
        return chunk

    def output_text(self) -> str:
        return self._out.decode("utf-8", errors="replace")

    def output_bytes(self) -> bytes:
        return bytes(self._out)


@dataclass
class ChildProcessDouble:
    """Fake child process with crash / EOF controls."""

    pid: int = 9001
    returncode: int | None = None
    stdout: ByteSplitStdio = field(default_factory=ByteSplitStdio)
    stdin: ByteSplitStdio = field(default_factory=ByteSplitStdio)
    stderr: ByteSplitStdio = field(default_factory=ByteSplitStdio)
    killed: bool = False
    on_kill: Callable[[], None] | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9
        if self.on_kill:
            self.on_kill()

    def terminate(self) -> None:
        self.returncode = -15

    def crash(self, code: int = 1) -> None:
        self.returncode = code

    def eof_stdout(self) -> None:
        # Leave input empty so subsequent reads return b"".
        self.stdout._in.clear()


@dataclass
class SidecarHarness:
    """Compose clock + split stdio + child failure knobs for protocol tests."""

    clock: FakeClock = field(default_factory=FakeClock)
    child: ChildProcessDouble = field(default_factory=ChildProcessDouble)
    utf8_chunk_size: int = 1

    def __post_init__(self) -> None:
        self.child.stdout.read_chunk_size = self.utf8_chunk_size
        self.child.stdin.read_chunk_size = self.utf8_chunk_size

    def feed_parent_to_child(self, line: str) -> None:
        if not line.endswith("\n"):
            line += "\n"
        self.child.stdin.feed_input(line)

    def feed_child_to_parent(self, line: str) -> None:
        if not line.endswith("\n"):
            line += "\n"
        self.child.stdout.feed_input(line)

    def set_byte_split(self, n: int) -> None:
        self.utf8_chunk_size = max(1, n)
        self.child.stdout.read_chunk_size = self.utf8_chunk_size
        self.child.stdin.read_chunk_size = self.utf8_chunk_size

    def force_child_failure(self, code: int = 1) -> None:
        self.child.crash(code)

    def force_write_fault(self) -> None:
        self.child.stdin.fail_on_write = True
