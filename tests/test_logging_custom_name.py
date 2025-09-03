from __future__ import annotations

import os
from pathlib import Path

from fast_app.app_provider import boot
from fast_app.utils.logging import get_log_file_path


def test_logging_uses_custom_file_name(tmp_path, monkeypatch):
    # Ensure fresh config
    monkeypatch.delenv("LOG_FILE_NAME", raising=False)

    custom_name = "module_x.log"

    # Point project root to a temp dir by faking utils/logging.py project_root resolution
    # The logger itself computes project_root relative to file location; we can instead
    # rely on the real repo root but ensure cleanup: write, then verify file exists

    boot(log_file_name=custom_name, autodiscovery=False)

    path = get_log_file_path()
    assert path is not None
    assert path.name == custom_name
    assert path.parent.name == "log"


