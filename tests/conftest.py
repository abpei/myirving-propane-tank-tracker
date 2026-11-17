"""Pytest bootstrap and shared fixtures for the parser test suite.

The parser module is pure Python (BeautifulSoup plus the integration constants),
but importing it through the normal package path executes
``custom_components/myirving_propane/__init__.py``, which imports Home
Assistant. These tests intentionally need neither Home Assistant nor a running
container, so when HA is not installed a lightweight package shell is registered
first and the parser submodule is imported beneath it.
"""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
import sys
import types

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
COMPONENT_DIR = REPO_ROOT / "custom_components" / "myirving_propane"
FIXTURE_DIR = TESTS_DIR / "fixtures"
USER_HOME_FIXTURE = FIXTURE_DIR / "user_home_scrubbed.html"


def _register_package_shell() -> None:
    """Register custom_components.myirving_propane without running its __init__.

    The shell keeps the real filesystem ``__path__`` so relative imports such as
    ``parser`` -> ``.const`` resolve normally. When Home Assistant is installed
    the shell is skipped and the real package is imported instead.
    """
    if find_spec("homeassistant") is not None:
        return

    custom_components = sys.modules.get("custom_components")
    if custom_components is None:
        custom_components = types.ModuleType("custom_components")
        custom_components.__path__ = [str(COMPONENT_DIR.parent)]
        sys.modules["custom_components"] = custom_components

    package = types.ModuleType("custom_components.myirving_propane")
    package.__path__ = [str(COMPONENT_DIR)]
    package.__package__ = "custom_components.myirving_propane"
    sys.modules["custom_components.myirving_propane"] = package


def _prepare_import_path() -> None:
    """Make the repository root importable and pre-register the package shell."""
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _register_package_shell()


_prepare_import_path()


@pytest.fixture(scope="session")
def user_home_html() -> str:
    """Return the scrubbed /user-home fixture exactly as it is committed."""
    return USER_HOME_FIXTURE.read_text(encoding="utf-8")
