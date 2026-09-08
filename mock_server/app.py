from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import sqlite3
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
import os

# ✅ 核心改造 1：引入我们的全局配置中心
from config import settings

# ========================================================
# 🛡️ 企业级日志基建 (Loguru)
# ========================================================
if not os.path.exists("logs"):
    os.makedirs("logs")

logger.add(
    "logs/server_{time:YYYY-MM-DD}.log", 
    rotation="00:00", 
    retention="7 days", 
    level="INFO", 
    encoding="utf-8"
)

app = FastAPI()

# 拦截并重写 FastAPI 默认的 422 报错
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    client_ip = request.client.host if request.client else "Unknown"
    logger.warning(f"🚨 [安全拦截 422] | 源IP: {client_ip} | 路径: {request.url.path} | 恶意Payload: {exc.body} | 拦截原因: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": "参数校验失败，非法请求已记录", "errors": exc.errors()}
    )

def init_db():
    # ✅ 核心改造 2：动态读取数据库名
    conn = sqlite3.connect(settings.DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS orders
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, qty INTEGER, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

class OrderRequest(BaseModel):
    item_name: str = Field(..., min_length=1, description="商品名不能为空")
    qty: int = Field(..., gt=0, le=1000000, description="订单数量必须在1到100万之间")

@app.post("/api/v1/login")
def login(username: str = "admin", password: str = "123456"):
    """模拟登录：账号密码正确则颁发 Token"""
    if username == "admin" and password == "123456":
        return {"code": 200, "message": "success", "token": "mock_token_888"}
    raise HTTPException(status_code=401, detail="账号或密码错误")

def verify_token(authorization: str = Header(None)):
    """依赖函数：检查请求头中的 Authorization 字段"""
    if not authorization or authorization != "Bearer mock_token_888":
        raise HTTPException(status_code=401, detail="无效或缺失的 Token，禁止访问！")
    return authorization

@app.post("/api/v1/orders")
def create_order(order: OrderRequest, token: str = Depends(verify_token)):
    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")
    
    # ✅ 核心改造 3：动态读取数据库名
    conn = sqlite3.connect(settings.DB_NAME)
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

from fastapi.responses import HTMLResponse
import time
import random

# ========================================================
# 🚀 第三阶段：QA 效能工具平台
# ========================================================

@app.get("/tools/data-factory", response_class=HTMLResponse)
def data_factory_ui():
    """造数工具的网页 UI，业务测试人员直接在浏览器打开使用"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>QA效能工具：一键造数据</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 50px; background-color: #f4f4f9; }
            .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 500px; margin: auto; text-align: center;}
            h2 { color: #333; margin-bottom: 30px;}
            input { padding: 10px; width: 80%; margin-bottom: 20px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px;}
            button { padding: 12px 24px; font-size: 16px; background-color: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; transition: 0.3s;}
            button:hover { background-color: #218838; box-shadow: 0 4px 8px rgba(40,167,69,0.3);}
            #result { margin-top: 25px; font-size: 18px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🛠️ 测开造数工厂</h2>
            <p style="color: #666; text-align: left; padding-left: 10%;">单次最高支持生成 100,000 条订单数据：</p>
            <input type="number" id="orderNum" value="10000" min="1" max="100000">
            <br>
            <button onclick="generateData()">🚀 点击一键秒级造数</button>
            <div id="result"></div>
        </div>
        
        <script>
            async function generateData() {
                const num = document.getElementById("orderNum").value;
                const resultDiv = document.getElementById("result");
                resultDiv.innerHTML = "🔄 数据库写入中，请稍候...";
                resultDiv.style.color = "orange";
                
                const response = await fetch(`/api/v1/tools/batch-orders?count=${num}`, { method: 'POST' });
                const data = await response.json();
                
                if(response.ok) {
                    resultDiv.style.color = "#28a745";
                    resultDiv.innerHTML = `✅ 成功！耗时: <b>${data.time_cost_seconds}</b> 秒，共生成 ${data.inserted_count} 条数据。`;
                } else {
                    resultDiv.style.color = "red";
                    resultDiv.innerHTML = `❌ 失败：${data.detail}`;
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/api/v1/tools/batch-orders")
def batch_create_orders(count: int = 1000):
    """供效能工具调用的批量造数接口 (跳过鉴权，直接打库)"""
    if count <= 0 or count > 100000:
        return {"error": "数量必须在 1 到 100,000 之间"}
        
    start_time = time.time()
    
    orders = []
    for _ in range(count):
        item_name = f"批量测试商品_SKU{random.randint(1000, 9999)}"
        orders.append((item_name, random.randint(1, 50), "PENDING"))
        
    # ✅ 核心改造 4：动态读取数据库名
    conn = sqlite3.connect(settings.DB_NAME)
    cursor = conn.cursor()
    
    cursor.executemany("INSERT INTO orders (item_name, qty, status) VALUES (?, ?, ?)", orders)
    
    conn.commit()
    conn.close()
    
    end_time = time.time()
    
    logger.info(f"✅ [性能工具] 成功批量灌入 {count} 条数据，耗时 {end_time - start_time:.3f} 秒")
    
    return {
        "message": "batch generation success",
        "inserted_count": count,
        "time_cost_seconds": round(end_time - start_time, 3)
    }