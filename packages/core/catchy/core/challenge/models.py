from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, field_validator

Directory = Annotated[
    Path,
    Field(...),
    PlainSerializer(lambda value: str(value), return_type=str, when_used="json"),
]


class Challenge(BaseModel):
    id: str
    description: str
    directory: Directory

    @field_validator("directory")
    @classmethod
    def validate_directory(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"directory does not exist: {value}")
        if not value.is_dir():
            raise ValueError(f"directory is not a directory: {value}")

        return value
