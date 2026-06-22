from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QIODevice, QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket


SINGLE_INSTANCE_SERVER_NAME = "StickyNotes.LocalInstance"


def notify_running_instance(
    server_name: str = SINGLE_INSTANCE_SERVER_NAME,
) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(server_name, QIODevice.OpenModeFlag.WriteOnly)
    if not socket.waitForConnected(250):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(250)
    socket.disconnectFromServer()
    return True


class SingleInstanceServer(QObject):
    def __init__(
        self,
        show_existing_windows: Callable[[], None],
        server_name: str = SINGLE_INSTANCE_SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._show_existing_windows = show_existing_windows
        self._server_name = server_name
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._handle_connection)

    def start(self) -> bool:
        # A client probe is the reliable cross-platform signal. QLocalServer.listen()
        # cannot be trusted to detect an existing instance: on Windows named pipes
        # allow several servers to listen on the same name, so a second launch would
        # happily listen() too and every instance would think it is the primary —
        # which is how multiple instances used to pile up. So probe first: if a live
        # instance answers we are a second launch and step aside (the probe also tells
        # that instance to surface its windows).
        if notify_running_instance(self._server_name):
            return False
        # No live instance answered. Clear any stale pipe/socket left behind by a
        # crashed process, then claim the lock.
        QLocalServer.removeServer(self._server_name)
        return self._server.listen(self._server_name)

    def _handle_connection(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is not None:
                connection.disconnectFromServer()
                connection.deleteLater()
        self._show_existing_windows()
