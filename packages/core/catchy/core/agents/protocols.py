from abc import ABC
from pathlib import Path
from typing import AsyncGenerator

from ..challenge.models import Challenge
from ..webhook.models import Webhook


class Agent(ABC):
    key: str

    def stream(
        self,
        challenge: Challenge,
        workspace: Path,
        metadata_directory: Path,
        webhook: Webhook | None = None,
    ) -> AsyncGenerator[str, str | None]: ...
