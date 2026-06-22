from __future__ import annotations

from uuid import uuid4

from PySide6.QtWidgets import QApplication

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
