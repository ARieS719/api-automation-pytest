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

from pydantic import BaseModel

# 子节点 1：定义 data 里面的字段
class ReqresDataModel(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    avatar: str

# 子节点 2：定义 support 里面的字段
class ReqresSupportModel(BaseModel):
    url: str
    text: str

# 根节点：把上面两个子节点拼装起来
class ReqresUserSchema(BaseModel):
    data: ReqresDataModel
    support: ReqresSupportModel