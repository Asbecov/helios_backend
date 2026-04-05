from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PlanResponse(BaseModel):
    """Represent plan response."""

    id: UUID
    name: str
    duration_days: int
    price: Decimal
    final_price: Decimal
    tags: dict[str, str]
