"""Transactional state fixture for 087, not a live Postgres locking proof."""

from contextlib import contextmanager
from threading import RLock


class Database:
    def __init__(self):
        self.row = None
        self.lock = RLock()
        self.fail_update = False
        self.unavailable = False
        self.options = []

    def connect(self, conninfo, **kwargs):
        if self.unavailable:
            raise OSError("database connection unavailable")
        self.options.append(kwargs)
        return Connection(self)


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def transaction(self):
        with self.db.lock:
            previous = self.db.row
            try:
                yield
            except BaseException:
                self.db.row = previous
                raise

    def execute(self, sql, params=()):
        if sql.startswith("CREATE TABLE"):
            return Result()
        if sql.startswith("INSERT INTO weighted_turn_state"):
            if self.db.row is None:
                self.db.row = tuple(params)
            return Result()
        if sql.startswith("SELECT policy, state FROM weighted_turn_state"):
            assert "FOR UPDATE" in sql
            return Result(self.db.row)
        if sql.startswith("UPDATE weighted_turn_state SET state"):
            if self.db.fail_update:
                raise OSError("simulated transaction write failure")
            self.db.row = (self.db.row[0], params[0])
            return Result()
        raise AssertionError(f"unsupported SQL: {sql}")

    def close(self):
        pass
