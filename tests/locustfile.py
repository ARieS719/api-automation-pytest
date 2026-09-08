from locust import HttpUser, task, between
import random

class OrderTestUser(HttpUser):
    # 模拟真实用户的行为：每次操作完，随机发呆 1 到 3 秒再进行下一次操作
    wait_time = between(1, 3)

    def on_start(self):
        """
        前置操作：每个模拟用户在开始狂刷接口前，只执行一次的登录动作。
        """
        resp = self.client.post("/api/v1/login", params={"username": "admin", "password": "123456"})
        if resp.status_code == 200:
            token = resp.json().get("token")
            # 把拿到的 Token 塞进这个用户的全局请求头里
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        else:
            print("登录失败，压测无法继续！")

    @task
    def create_order_task(self):
        """
        核心任务：这就是成百上千个用户会疯狂循环点击的动作。
        """
        payload = {
            "item_name": "性能压测专用传感器",
            "qty": random.randint(1, 100)
        }
        
        # 发送请求，开启 catch_response=True 以便我们自定义断言
        with self.client.post("/api/v1/orders", json=payload, name="创建订单接口", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"订单创建失败，状态码: {response.status_code}")