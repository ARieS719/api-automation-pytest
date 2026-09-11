# tests/test_order.py
import pytest
from config import settings as app_config

class TestOrderLifecycle:
    """
    企业级多链路状态流转测试套件
    """

    def test_full_order_lifecycle(self, auth_session, db_connection):
        print("\n--- [Test START] 开始执行多链路订单生命周期测试 ---")
        
        # ==========================================
        # 阶段一：正向链路 - 创建订单
        # ==========================================
        create_url = f"{app_config.BASE_URL}/api/v1/orders"
        payload = {"item_name": "工业级机械臂_QA测试", "qty": 2}
        
        # 发起下单请求
        resp_create = auth_session.post(create_url, json=payload)
        assert resp_create.status_code == 200, f"下单失败: {resp_create.text}"
        
        order_id = resp_create.json().get("data").get("order_id")
        print(f"-> [步骤1] 下单成功，获取到订单 ID: {order_id}")
        
        # 【深度断言1】：检查数据库落库状态是否为初始的 PENDING
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT status, qty FROM orders WHERE id=%s", (order_id,))
            db_record = cursor.fetchone()
        
        assert db_record is not None, "数据库中未找到该订单"
        assert db_record['status'] == "PENDING", "订单初始状态异常"
        assert db_record['qty'] == 2, "订单落库数量错误"
        print("-> [断言1] 数据库落库校验通过 (PENDING)！")

        # ==========================================
        # 阶段二：正向链路 - 支付订单
        # ==========================================
        pay_url = f"{app_config.BASE_URL}/api/v1/orders/{order_id}/pay"
        resp_pay = auth_session.post(pay_url)
        assert resp_pay.status_code == 200, "支付接口调用失败"
        print(f"-> [步骤2] 订单 {order_id} 支付接口调用成功")
        
        # 【深度断言2】：检查数据库状态是否正确扭转为 PAID
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
            db_record = cursor.fetchone()
            
        assert db_record['status'] == "PAID", "订单支付后，数据库状态未流转为 PAID"
        print("-> [断言2] 数据库状态流转校验通过 (PAID)！")

        # ==========================================
        # 阶段三：逆向防线 - 已支付订单禁止取消 (状态机防御)
        # ==========================================
        cancel_url = f"{app_config.BASE_URL}/api/v1/orders/{order_id}/cancel"
        resp_cancel = auth_session.post(cancel_url)
        
        # 期望触发我们业务代码里写的 HTTP 409 状态冲突拦截
        assert resp_cancel.status_code == 409, "状态机防御失效：已支付订单不应允许被取消！"
        print("-> [步骤3] 状态机防御生效，成功拦截已支付订单的非法取消请求")
        
        # 【深度断言3】：验证底层数据没有被并发或脏读篡改，依然是 PAID
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
            db_record = cursor.fetchone()
            
        assert db_record['status'] == "PAID", "严重Bug：接口防御虽拦截，但底层数据被意外篡改！"
        print("-> [断言3] 底层数据安全校验通过，状态依然保持 PAID。")