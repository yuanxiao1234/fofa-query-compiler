from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def workspace_factory(tmp_path: Path) -> Callable[[str], Path]:
    """Create isolated workspace roots without sharing mutable state."""

    def create(name: str = "workspace") -> Path:
        path = tmp_path / name
        path.mkdir()
        return path

    return create
