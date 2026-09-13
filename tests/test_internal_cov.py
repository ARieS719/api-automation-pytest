import pytest
from fastapi.testclient import TestClient

# 这里的导入动作，就会把 app.py 加载到 pytest 的进程里！
from mock_server.app import app 

client = TestClient(app)

def test_coverage_magic():
    """
    这个测试用例不走真实的 8000 端口，
    而是直接在 pytest 内部把微服务加载进来打一次，
    这样 pytest-cov 就能精确统计到到底走了哪行代码！
    """
    # 打一下登录接口
    response = client.post(
        "/api/v1/login",
        data={"username": "qa_admin", "password": "qa_password"}
    )
    assert response.status_code == 200
    
    # 随便打一个库存查询接口
    res2 = client.get("/api/v1/inventory/sku_1001")
    assert res2.status_code == 200