import socket
from contextlib import contextmanager
from unittest.mock import patch

from app.collectors.tcp import collect_tcp


@contextmanager
def _fake_socket():
    yield object()


def test_collect_tcp_open():
    with patch("socket.create_connection", return_value=_fake_socket()):
        result = collect_tcp("example.com", 443)

    assert result.status == "open"
    assert result.error is None


def test_collect_tcp_refused():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        result = collect_tcp("example.com", 443)

    assert result.status == "refused"


def test_collect_tcp_reset():
    with patch("socket.create_connection", side_effect=ConnectionResetError("reset")):
        result = collect_tcp("example.com", 443)

    assert result.status == "reset"


def test_collect_tcp_timeout():
    with patch("socket.create_connection", side_effect=socket.timeout("timed out")):
        result = collect_tcp("example.com", 443)

    assert result.status == "timeout"


def test_collect_tcp_unresolvable_host_is_unmeasured_not_guessed():
    with patch("socket.create_connection", side_effect=socket.gaierror("name resolution failed")):
        result = collect_tcp("does-not-exist.invalid", 443)

    assert result.status is None
    assert result.error is not None
