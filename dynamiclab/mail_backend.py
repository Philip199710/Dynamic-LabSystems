"""SMTP email backend that only ever connects to the mail server over IPv4.

This app's hosting (Render) doesn't have a working outbound IPv6 route, but
DNS for some mail providers — Gmail included — returns an IPv6 address
before an IPv4 one. Python's smtplib tries addresses in that order and
gives up immediately with "OSError: [Errno 101] Network is unreachable" on
the very first (IPv6) attempt instead of falling through to IPv4.

This backend is identical to Django's built-in SMTP backend, except the
socket connection is restricted to IPv4 addresses, so that failure mode
never happens.
"""

import smtplib
import socket

from django.core.mail.backends.smtp import EmailBackend as _DjangoSMTPBackend


def _ipv4_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Same contract as socket.create_connection, but only tries AF_INET
    (IPv4) addresses returned for the host — never AF_INET6."""
    host, port = address
    error = None
    for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    ):
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            error = exc
            if sock is not None:
                sock.close()
    if error is not None:
        raise error
    raise OSError(f"getaddrinfo returned no IPv4 addresses for {host}")


class IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        if timeout is not None and not timeout:
            raise ValueError("Non-blocking socket (timeout=0) is not supported")
        return _ipv4_create_connection((host, port), timeout, self.source_address)


class IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        new_socket = IPv4SMTP._get_socket(self, host, port, timeout)
        return self.context.wrap_socket(new_socket, server_hostname=self._host)


class EmailBackend(_DjangoSMTPBackend):
    """Django's SMTP backend, with connections forced over IPv4 (see
    module docstring)."""

    @property
    def connection_class(self):
        return IPv4SMTP_SSL if self.use_ssl else IPv4SMTP
