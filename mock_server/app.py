from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import sqlite3

app = FastAPI()

def init_db():
    conn = sqlite3.connect("test_business.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS orders
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, qty INTEGER, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

class OrderRequest(BaseModel):
    item_name: str
    qty: int

# ================= 核心新增：登录接口 =================
@app.post("/api/v1/login")
def login(username: str = "admin", password: str = "123456"):
    """模拟登录：账号密码正确则颁发 Token"""
    if username == "admin" and password == "123456":
        return {"code": 200, "message": "success", "token": "mock_token_888"}
    raise HTTPException(status_code=401, detail="账号或密码错误")

# ================= 核心新增：保安大叔查 Token =================
def verify_token(authorization: str = Header(None)):
    """依赖函数：检查请求头中的 Authorization 字段"""
    if not authorization or authorization != "Bearer mock_token_888":
        raise HTTPException(status_code=401, detail="无效或缺失的 Token，禁止访问！")
    return authorization

# ================= 修改原有接口：强制要求 Token =================
# 在函数的参数里加上 token: str = Depends(verify_token)
@app.post("/api/v1/orders")
def create_order(order: OrderRequest, token: str = Depends(verify_token)):
    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")
    
    conn = sqlite3.connect("test_business.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (item_name, qty, status) VALUES (?, ?, ?)", 
                   (order.item_name, order.qty, "PENDING"))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "order_id": order_id,
            "item_name": order.item_name,
            "current_status": "PENDING",
            "timestamp": 1690000000
        }
    }