# tests/conftest.py
import pytest
import requests
import pymysql  # ✅ 核心升级：接入企业级 MySQL 驱动
from config import settings as app_config

@pytest.fixture(scope="session")
def auth_session():
    """
    全局鉴权夹具：自动登录并维持 Session。
    """
    print("\n[Fixture启动] 正在进行全局登录并获取 Token...")
    session = requests.Session()
    login_url = f"{app_config.BASE_URL}/api/v1/login"
    
    try:
        resp = session.post(login_url, params={"username": "admin", "password": "123456"}, timeout=3)
        token = resp.json().get("token")
        if not token:
            pytest.fail("致命错误：无法获取 Token，鉴权失败！")
            
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"[Fixture启动] Token 注入成功 (截断显示): {token[:10]}...")
    except Exception as e:
        pytest.fail(f"登录接口请求异常，请检查 Mock 服务是否启动: {str(e)}")
        
    yield session
    
    print("\n[Fixture结束] 测试执行完毕，销毁全局 HTTP Session。")
    session.close()


# ✅ 核心升维 1：建立一个贯穿全局的数据库连接
@pytest.fixture(scope="session")
def db_connection():
    """
    全局数据库连接夹具 (Session级别)：
    在所有测试开始前建立一次连接，所有测试结束后断开，避免频繁消耗数据库连接数。
    """
    print("\n[DB连接] 正在连接 Docker 测试数据库...")
    # 这里直接连接我们刚在 docker-compose 中配置的账号密码
    # 真实项目中，这些敏感信息也应提取到 config.py 或环境变量中
    connection = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='qa_user',
        password='qa_pass',
        database='automation_shop',
        charset='utf8mb4',
        # 【杀手锏配置】让查询结果返回字典而不是元组，极大地简化了测试断言！
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True  # 关闭自动提交，我们在代码里手动 commit 确保安全
    )
    yield connection
    
    print("\n[DB连接] 所有测试结束，断开数据库连接。")
    connection.close()


# ✅ 核心升维 2：优雅的数据清理闭环
@pytest.fixture(scope="function")
def cleanup_order_db(db_connection):
    """
    订单业务的专属后置清理夹具 (Function级别)。
    注意这里括号里的 db_connection，Pytest 会自动把上面建好的连接传进来！
    """
    # yield 前的 Setup，什么都不做，直接把控制权交给测试用例
    yield 
    
    # yield 后的 Teardown：测试用例跑完（无论成功失败）必然执行的代码
    print("\n[数据清理] 开始执行订单表脏数据清理...")
    try:
        with db_connection.cursor() as cursor:
            # 专业的做法是：只清理特定特征的测试数据，例如订单号带有 "QA_AUTO_" 前缀的
            sql = "DELETE FROM orders WHERE order_no LIKE %s"
            cursor.execute(sql, ('QA_AUTO_%',))
            deleted_rows = cursor.rowcount
            
        # 必须显式提交事务
        db_connection.commit()
        print(f"[数据清理] 完毕，安全清理了 {deleted_rows} 条以 QA_AUTO_ 开头的垃圾订单。")
        
    except Exception as e:
        db_connection.rollback()
        print(f"[数据清理异常] 回滚事务: {str(e)}")