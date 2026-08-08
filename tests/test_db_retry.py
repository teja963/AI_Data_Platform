from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from core.db import run_with_database_retry


def test_database_retry_recovers_after_transient_connection_failures():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OperationalError("connect", {}, RuntimeError("Neon is waking"))
        return "connected"

    with patch("core.db.engine.dispose") as dispose, patch("core.db.time.sleep") as sleep:
        assert run_with_database_retry(operation) == "connected"

    assert attempts == 3
    assert dispose.call_count == 2
    assert [call.args[0] for call in sleep.call_args_list] == [0.75, 1.5]

