import queue
import pymysql
import random
from locust import HttpUser, task, between, events
from locust.exception import StopUser

# ========================================================
# 🚀 压测全局基建：内存数据队列
# ========================================================
# 用于存放从数据库中拉取的、等待被支付的真实订单 ID
pending_orders = queue.Queue()

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    压测前置钩子：在所有虚拟用户发兵之前，只执行一次！
    作用：直连数据库，将之前造好的海量订单吃进内存，避免压测时频繁读库成为性能瓶颈。
    """
    print("\n[压测引擎初始化] 正在连接底层数据库，装载弹药...")
    try:
        conn = pymysql.connect(
            host='127.0.0.1', port=3306, user='qa_user', password='qa_pass',
            database='automation_shop', cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cursor:
            # 动态拉取最多 50000 条未支付订单，供并发大军消费
            cursor.execute("SELECT id FROM orders WHERE status = 'PENDING' LIMIT 50000")
            records = cursor.fetchall()
            for row in records:
                pending_orders.put(row['id'])
        conn.close()
        print(f"✅ [压测引擎就绪] 成功装载 {pending_orders.qsize()} 条待支付订单进入内存队列！\n")
    except Exception as e:
        print(f"❌ 致命错误：压测数据装载失败: {e}")

# ========================================================
# ⚔️ 并发执行者：虚拟用户行为定义
# ========================================================
class OrderTestUser(HttpUser):
    # 将等待时间缩短，提升压测狂暴程度 (0.5 - 1.5秒之间随机)
    wait_time = between(0.5, 1.5)

    def on_start(self):
        """每个虚拟用户诞生时的唯一动作：登录并拿 Token"""
        # 为了防止第一下就被服务器拒绝报错，我们可以加个异常捕获
        try:
            resp = self.client.post("/api/v1/login", params={"username": "admin", "password": "123456"})
            if resp.status_code == 200:
                token = resp.json().get("token")
                self.client.headers.update({"Authorization": f"Bearer {token}"})
            else:
                print(f"登录失败，状态码: {resp.status_code}，该虚拟用户被销毁！")
                # ✅ 核心修复：一旦拿不到 Token，直接杀死这个并发用户，防止它后续引发 401 雪崩
                raise StopUser()
        except Exception as e:
            print(f"连接服务器失败，虚拟用户阵亡: {e}")
            raise StopUser()

    @task(3) # 权重 3：代表大概 30% 的流量是下单行为
    def create_order_task(self):
        payload = {
            "item_name": f"大促压测商品_SKU_{random.randint(100, 999)}",
            "qty": random.randint(1, 100)
        }
        with self.client.post("/api/v1/orders", json=payload, name="[写请求] 创建订单", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"下单异常: {response.status_code}")

    @task(7) # 权重 7：代表大概 70% 的核心并发流量在疯狂支付
    def pay_order_task(self):
        try:
            # 线程安全地弹出一个订单 ID，block=False 保证队列空了不会卡死
            order_id = pending_orders.get(block=False)
        except queue.Empty:
            # 如果造的数据被消耗光了，这个动作就不再执行
            return 

        # 向支付接口发起核心并发冲击
        with self.client.post(f"/api/v1/orders/{order_id}/pay", name="[写请求] 订单状态流转 (支付)", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 409:
                # 亮点：在极端并发下，如果出现状态冲突，能返回 409 说明你的状态机防御逻辑起作用了！
                # 这不是压测失败，而是系统防御成功的表现！
                response.success()
            else:
                response.failure(f"支付链路崩溃，状态码: {response.status_code}")

# ... 之前 OrderTestUser 的代码保留 ...

class SecKillUser(HttpUser):
    # 秒杀不需要思考时间，零延迟发兵
    wait_time = between(0, 0)
    
    @task
    def rush_buy(self):
        # 所有人都向 sku_1001 发起强攻，不顾一切
        with self.client.post("/api/v1/seckill/sku_1001", name="[秒杀洪峰] 抢购商品", catch_response=True) as response:
            # 无论成功还是失败，在压测层面我们都算作"请求发出去了"，方便在面板上看并发量
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"接口异常: {response.status_code}")