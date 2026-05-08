from abc import ABC
from pathlib import Path
from typing import AsyncIterator

from ..challenge.models import Challenge


class Agent(ABC):
    key: str

    def stream(self, challenge: Challenge, workspace: Path) -> AsyncIterator[str]: ...
