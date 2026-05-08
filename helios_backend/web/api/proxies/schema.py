from pydantic import BaseModel


class ProxyResponse(BaseModel):
    """Represent proxy response."""

    url: str
    added_at: str