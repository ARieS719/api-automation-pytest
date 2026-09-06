import pytest
import requests
import sqlite3
from .schemas import OrderResponseSchema
from pydantic import ValidationError
from .utils import read_yaml_data

BASE_URL = "http://127.0.0.1:8000"

class TestOrderAPI:
    
    # 只需要在括号里，把刚才写的 cleanup_order_db 加上！
    def test_create_order_success_and_db_consistency(self, auth_session, cleanup_order_db):
        """测试正向流程：创建订单并在数据库对账 (数据强一致性断言)"""
        
        # 1. 准备数据 & 发送请求
        payload = {"item_name": "工业级传感器V2", "qty": 100}
        resp = auth_session.post(f"{BASE_URL}/api/v1/orders", json=payload)
        
        # 2. 基础断言
        assert resp.status_code == 200
        
        # 3. 强契约校验
        try:
            parsed_resp = OrderResponseSchema(**resp.json())
        except ValidationError as e:
            pytest.fail(f"接口返回的数据结构发生破坏性变更: {e}")
            
        # 4. 数据强一致性断言
        order_id = parsed_resp.data.order_id
        conn = sqlite3.connect("test_business.db")
        cursor = conn.cursor()
        cursor.execute("SELECT item_name, status FROM orders WHERE id=?", (order_id,))
        db_record = cursor.fetchone()
        conn.close()
        
        assert db_record is not None, "数据库中未生成对应的订单数据！"
        assert db_record[0] == payload["item_name"], "数据库商品名称不一致"
        assert db_record[1] == "PENDING", "初始业务状态错误"

    # ================= 核心修复部分 =================
    @pytest.mark.parametrize("case_data", read_yaml_data("order_abnormal_cases.yaml"))
    def test_create_order_abnormal(self, auth_session, case_data):
        """测试异常流程：读取 YAML 实现纯数据驱动验证"""
        
        # 从 case_data 字典中解包数据
        case_title = case_data["case_title"]
        payload = case_data["payload"]
        expected_status = case_data["expected_status"]
        expected_msg = case_data["expected_msg"]
        
        resp = auth_session.post(f"{BASE_URL}/api/v1/orders", json=payload)
        
        assert resp.status_code == expected_status, f"[{case_title}] 状态码错误"
        assert expected_msg in resp.text, f"[{case_title}] 提示信息未包含预期内容"