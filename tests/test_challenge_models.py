from pathlib import Path

import pytest
from pydantic import ValidationError

from catchy.core.challenge.models import Challenge


def test_challenge_accepts_existing_directory(tmp_path: Path) -> None:
    challenge = Challenge(
        id="lets-change",
        description="A small reversing challenge.",
        directory=tmp_path,
    )

    assert challenge.directory == tmp_path
    assert challenge.model_dump(mode="json")["directory"] == str(tmp_path)


def test_challenge_rejects_missing_directory(tmp_path: Path) -> None:
    missing_directory = tmp_path / "missing"

    with pytest.raises(ValidationError, match="directory does not exist"):
        Challenge(
            id="missing",
            description="This source directory has not been created.",
            directory=missing_directory,
        )


def test_challenge_rejects_file_directory(tmp_path: Path) -> None:
    source_file = tmp_path / "source.txt"
    source_file.write_text("not a directory")

    with pytest.raises(ValidationError, match="directory is not a directory"):
        Challenge(
            id="file",
            description="The source path points at a file.",
            directory=source_file,
        )
