"""Fill vendor/ with the Linux packages the Docker image copies in.

Run this inside the Docker base image, so the packages match the container rather than the host.
It only needs running again when the dependencies in pyproject.toml change:

    docker run --rm -v "${PWD}:/project" -w /project python:3.14-slim python scripts/vendor_deps.py
"""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

VENDOR_DIR = Path("vendor")


def main() -> None:
    """Replace vendor/ with the runtime and test dependencies pinned in pyproject.toml."""
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    packages = [*project["dependencies"], *project["optional-dependencies"]["test"]]

    shutil.rmtree(VENDOR_DIR, ignore_errors=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "--root-user-action=ignore",
            "--target",
            str(VENDOR_DIR),
            *packages,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
