"""Show version information."""

import argparse
from pathlib import Path
from importlib import metadata as importlib_metadata
import tomllib

from .command_base import CommandBase


class VersionCommand(CommandBase):
    """Command to show version information."""

    @property
    def name(self) -> str:
        return "version"

    @property
    def help(self) -> str:
        return "Show version information"

    def _get_version(self) -> str:
        """Resolve version from pyproject.toml, fallback to package metadata."""
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            project_section = data.get("project", {})
            version_value = project_section.get("version")
            if isinstance(version_value, str) and version_value:
                return version_value
        except Exception:
            pass

        try:
            return importlib_metadata.version("fast-app")
        except importlib_metadata.PackageNotFoundError:
            return "unknown"

    def execute(self, args: argparse.Namespace) -> None:
        """Show version and author information."""
        version = self._get_version()
        print(f"FastApp v{version}")