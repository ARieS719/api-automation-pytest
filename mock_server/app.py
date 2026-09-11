from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from loguru import logger
import time
import random
import os
import pymysql # ✅ 核心切换：引入 MySQL 驱动
from config import settings

# ========================================================
# 🛡️ 企业级日志基建 (Loguru) - 保持不变
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

# 拦截并重写 FastAPI 默认的 422 报错 - 保持不变
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    client_ip = request.client.host if request.client else "Unknown"
    logger.warning(f"🚨 [安全拦截 422] | 源IP: {client_ip} | 路径: {request.url.path} | 恶意Payload: {exc.body} | 拦截原因: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "参数校验失败，非法请求已记录", "errors": exc.errors()}
    )

# ✅ 核心改造 1：建立直连 Docker MySQL 的工厂函数
def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='qa_user',
        password='qa_pass',
        database='automation_shop',
        cursorclass=pymysql.cursors.DictCursor
    )

# ⚠️ 注意：删除了原有的 init_db()，因为我们在 Docker 里的 01_create_tables.sql 已经做了表初始化

class OrderRequest(BaseModel):
    item_name: str = Field(..., min_length=1, description="商品名不能为空")
    qty: int = Field(..., gt=0, le=1000000, description="订单数量必须在1到100万之间")

@app.post("/api/v1/login")
def login(username: str = "admin", password: str = "123456"):
    if username == "admin" and password == "123456":
        return {"code": 200, "message": "success", "token": "mock_token_888"}
    raise HTTPException(status_code=401, detail="账号或密码错误")

def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != "Bearer mock_token_888":
        raise HTTPException(status_code=401, detail="无效或缺失的 Token，禁止访问！")
    return authorization

@app.post("/api/v1/orders")
def create_order(order: OrderRequest, token: str = Depends(verify_token)):
    if order.qty <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")
    
    # ✅ 核心改造 2：替换为 MySQL 的连接方式与 %s 占位符
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 注意：MySQL 的占位符是 %s，不是 SQLite 的 ?
            sql = "INSERT INTO orders (item_name, qty, status) VALUES (%s, %s, %s)"
            cursor.execute(sql, (order.item_name, order.qty, "PENDING"))
            order_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        logger.error(f"落库失败: {str(e)}")
        raise HTTPException(status_code=500, detail="数据库内部错误")
    finally:
        conn.close()
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "order_id": order_id,
            "item_name": order.item_name,
            "current_status": "PENDING",
            "timestamp": int(time.time())
        }
    }

# ========================================================
# 🚀 第三阶段：QA 效能工具平台 (UI代码完全保留)
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
    if count <= 0 or count > 100000:
        return {"error": "数量必须在 1 到 100,000 之间"}
        
    start_time = time.time()
    orders = []
    for _ in range(count):
        item_name = f"批量测试商品_SKU{random.randint(1000, 9999)}"
        orders.append((item_name, random.randint(1, 50), "PENDING"))
        
    # ✅ 核心改造 3：批量插入改用 MySQL 语法
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO orders (item_name, qty, status) VALUES (%s, %s, %s)"
            cursor.executemany(sql, orders)
        conn.commit()
    finally:
        conn.close()
    
    end_time = time.time()
    logger.info(f"✅ [性能工具] 成功批量灌入 {count} 条数据，耗时 {end_time - start_time:.3f} 秒")
    return {
        "message": "batch generation success",
        "inserted_count": count,
        "time_cost_seconds": round(end_time - start_time, 3)
    }

# ================= 新增业务：订单状态机逻辑 =================
@app.post("/api/v1/orders/{order_id}/pay")
def pay_order(order_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="订单不存在")
                
            current_status = row['status'] # 使用了 DictCursor，所以可以直接拿 key
            
            if current_status == "PAID":
                raise HTTPException(status_code=409, detail="订单已支付，请勿重复支付")
            if current_status == "CANCELLED":
                raise HTTPException(status_code=409, detail="订单已取消，无法支付")
                
            cursor.execute("UPDATE orders SET status='PAID' WHERE id=%s", (order_id,))
        conn.commit()
    finally:
        conn.close()
    
    return {"code": 0, "msg": "支付成功", "data": {"order_id": order_id, "status": "PAID"}}


@app.post("/api/v1/orders/{order_id}/cancel")
def cancel_order(order_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="订单不存在")
                
            current_status = row['status']
            
            if current_status == "PAID":
                raise HTTPException(status_code=409, detail="订单已支付，无法取消。请走退款流程。")
            if current_status == "CANCELLED":
                raise HTTPException(status_code=409, detail="订单已取消，请勿重复操作")
                
            cursor.execute("UPDATE orders SET status='CANCELLED' WHERE id=%s", (order_id,))
        conn.commit()
    finally:
        conn.close()
    
    return {"code": 0, "msg": "取消成功", "data": {"order_id": order_id, "status": "CANCELLED"}}