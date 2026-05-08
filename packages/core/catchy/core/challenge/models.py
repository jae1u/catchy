from pydantic import BaseModel


class Challenge(BaseModel):
    description: str
