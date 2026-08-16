"""Shared Qt session for widget/inbox tests."""

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["rctrl-qt-tests"])
    return app
