# tests/conftest.py
import pytest
import requests
import sqlite3

# ✅ 核心改造 1：引入我们在 config.py 中写的全局配置
from config import settings as app_config

# ❌ 删除了这行硬编码：BASE_URL = "http://127.0.0.1:8000"

# scope="session" 意味着这个函数在整个测试跑完前，只会被执行一次！
@pytest.fixture(scope="session")
def auth_session():
    """
    全局鉴权夹具：自动登录并维持 Session。
    """
    print("\n[Fixture启动] 正在进行全局登录并获取 Token...")
    
    # 1. 创建一个“带记忆的浏览器”（Session）
    session = requests.Session()
    
    # 2. 调用刚刚写的登录接口
    # ✅ 核心改造 2：发送请求时，动态读取配置中的 BASE_URL
    login_url = f"{app_config.BASE_URL}/api/v1/login"
    # 顺手加上 timeout=3，防止服务器没启好导致 pytest 死锁卡住！
    resp = session.post(login_url, params={"username": "admin", "password": "123456"}, timeout=3)
    
    # 3. 提取 Token
    token = resp.json().get("token")
    if not token:
        pytest.fail("致命错误：无法获取 Token，后面的测试没法跑了！")
        
    # 4. 把 Token 塞进 Session 的全局请求头里 (最关键的一步！)
    # 以后只要用这个 session 发请求，都会自动带上这句话
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"[Fixture启动] Token 注入成功: {token}")
    
    # 5. 把这个配置好的 session 丢给所有的测试用例去用
    yield session
    
    # 6. yield 后面的代码，会在所有测试用例执行【结束】后，自动执行（相当于清理工）
    print("\n[Fixture结束] 测试执行完毕，销毁全局 Session。")
    session.close()


# scope="function" 表示这个清理动作，每次跑完一个测试函数，都要执行一次
@pytest.fixture(scope="function")
def cleanup_order_db():
    """
    后置清理夹具：测试完成后，去数据库里删掉刚刚产生的那条脏数据。
    """
    print("\n[数据清理前置] 准备执行测试...")
    
    # yield 之前的代码是前置（Setup），这里我们不需要做什么特殊前置，直接进入测试
    yield  
    
    # ------------------ 分界线 ------------------
    # yield 之后的代码就是后置清理（Teardown），哪怕前面的断言失败报错了，这里的代码依然会强制执行！
    print("\n[数据清理后置] 测试结束，开始清理垃圾订单数据...")
    
    # ✅ 核心改造 3：底层数据库连接，动态读取配置中的 DB_NAME
    conn = sqlite3.connect(app_config.DB_NAME)
    cursor = conn.cursor()
    
    # 为了安全起见，我们只删除特定名称的测试订单，以免误删了别人的正常数据
    cursor.execute("DELETE FROM orders WHERE item_name = ?", ("工业级传感器V2",))
    deleted_rows = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"[数据清理后置] 清理完成，共删除了 {deleted_rows} 条脏数据！")