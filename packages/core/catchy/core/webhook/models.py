from pydantic import BaseModel


class Webhook(BaseModel):
    url: str
    preferred_language: str | None = None
