from datetime import date
from pydantic import BaseModel

class ActiveServerResponse(BaseModel):
    """Represents response data for Active Server"""

    server_name : str
    server_address : str
    added_at : str
    