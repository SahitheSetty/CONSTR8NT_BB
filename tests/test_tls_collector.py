import socket
import ssl
from unittest.mock import MagicMock, patch

from app.collectors.tls import collect_tls


def _fake_tcp_socket():
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.__exit__.return_value = False
    return sock


def test_collect_tls_ok():
    fake_sock = _fake_tcp_socket()
    fake_wrapped = MagicMock()
    fake_wrapped.__enter__.return_value = fake_wrapped
    fake_wrapped.__exit__.return_value = False

    with patch("socket.create_connection", return_value=fake_sock), \
         patch.object(ssl.SSLContext, "wrap_socket", return_value=fake_wrapped):
        result = collect_tls("example.com")

    assert result.handshake == "ok"
    assert result.error is None


def test_collect_tls_expired_cert_is_classified():
    error = ssl.SSLCertVerificationError()
    error.verify_message = "certificate has expired"

    with patch("socket.create_connection", return_value=_fake_tcp_socket()), \
         patch.object(ssl.SSLContext, "wrap_socket", side_effect=error):
        result = collect_tls("example.com")

    assert result.handshake == "expired_cert"


def test_collect_tls_unrecognised_verification_failure_is_unmeasured():
    error = ssl.SSLCertVerificationError()
    error.verify_message = "some brand new failure reason openssl invented"

    with patch("socket.create_connection", return_value=_fake_tcp_socket()), \
         patch.object(ssl.SSLContext, "wrap_socket", side_effect=error):
        result = collect_tls("example.com")

    assert result.handshake is None


def test_collect_tls_timeout():
    with patch("socket.create_connection", side_effect=socket.timeout("timed out")):
        result = collect_tls("example.com")

    assert result.handshake == "handshake_timeout"


def test_collect_tls_connection_refused_is_unmeasured():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        result = collect_tls("example.com")

    assert result.handshake is None
