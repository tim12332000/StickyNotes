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
        if self._server.listen(self._server_name):
            return True
        QLocalServer.removeServer(self._server_name)
        return self._server.listen(self._server_name)

    def _handle_connection(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is not None:
                connection.disconnectFromServer()
                connection.deleteLater()
        self._show_existing_windows()
