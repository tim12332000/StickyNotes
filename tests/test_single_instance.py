from __future__ import annotations

from uuid import uuid4

import pytest

from PySide6.QtWidgets import QApplication

from app import single_instance
from app.single_instance import SingleInstanceServer, notify_running_instance


def test_second_launch_notifies_running_instance() -> None:
    application = QApplication.instance() or QApplication([])
    server_name = f"StickyNotes.Test.{uuid4()}"
    activations: list[bool] = []
    server = SingleInstanceServer(
        lambda: activations.append(True),
        server_name=server_name,
        parent=application,
    )

    assert server.start()
    assert notify_running_instance(server_name)
    application.processEvents()

    assert activations == [True]


def test_second_instance_does_not_reclaim_a_live_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    server_name = f"StickyNotes.Test.{uuid4()}"
    primary = SingleInstanceServer(
        lambda: None, server_name=server_name, parent=application
    )
    assert primary.start()

    # Construct the second instance with the real QLocalServer, then record any
    # attempt to reclaim the lock. The live primary answers the probe, so start()
    # must step aside without removeServer() — reclaiming a live lock is exactly
    # what previously let several instances run at once.
    secondary = SingleInstanceServer(
        lambda: None, server_name=server_name, parent=application
    )
    reclaim_calls: list[str] = []

    class RecordingServer:
        @staticmethod
        def removeServer(name: str) -> bool:
            reclaim_calls.append(name)
            return True

    monkeypatch.setattr(single_instance, "QLocalServer", RecordingServer)

    try:
        assert secondary.start() is False
        assert reclaim_calls == []
    finally:
        primary._server.close()
        secondary._server.close()
