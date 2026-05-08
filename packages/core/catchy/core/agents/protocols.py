from abc import ABC
from pathlib import Path
from typing import AsyncIterator

from ..challenge.models import Challenge
from ..webhook.models import Webhook


class Agent(ABC):
    key: str

    def stream(
        self, challenge: Challenge, workspace: Path, webhook: Webhook | None = None
    ) -> AsyncIterator[str]: ...
