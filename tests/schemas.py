# tests/schemas.py
from pydantic import BaseModel, Field

class OrderDataModel(BaseModel):
    order_id: int
    item_name: str
    current_status: str
    timestamp: int

class OrderResponseSchema(BaseModel):
    code: int = Field(..., description="业务状态码")
    message: str
    data: OrderDataModel