import pytest
import requests
import concurrent.futures

# 既然本地服务和 Redis 都已经在跑了，我们直接打本地的测试环境
BASE_URL = "http://127.0.0.1:8000/api/v1"

@pytest.fixture
def setup_test_inventory():
    """
    测试前置准备：利用 Python 的 requests 库，
    向系统强行注入一个只有 1 件库存的测试商品。
    (注意：由于我们用的是内存字典，这步实际上需要我们在微服务加个临时注入接口，
     但为了演示，我们可以通过先疯狂消耗到只剩 1 件，或者直接开个测试后门。
     这里我们假定微服务里有一个初始化测试数据的接口，我马上带你加进去)
    """
    requests.post(f"{BASE_URL}/tools/init-test-stock/sku_test_lock/1")
    yield
    # 测试后清理工作可以在这里做

def test_redis_lock_prevents_overselling(setup_test_inventory):
    """
    核心并发用例：验证 Redis 锁能阻挡 5 个同时发起的并发请求
    """
    target_sku = "sku_test_lock"
    concurrent_users = 5
    
    # 定义一个将被多线程同时执行的请求函数
    def send_seckill_request():
        return requests.post(f"{BASE_URL}/seckill/{target_sku}")

    results = []
    
    # 🌟 高阶技巧：使用 ThreadPoolExecutor 强行制造瞬间并发
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        # submit 会把任务丢进线程池，并立即返回一个 Future 对象，不会阻塞
        futures = [executor.submit(send_seckill_request) for _ in range(concurrent_users)]
        
        # as_completed 会在某个请求完成时返回结果
        for future in concurrent.futures.as_completed(futures):
            response = future.result()
            results.append(response.json())

    # --- 开始核心断言分析 ---
    success_count = sum(1 for res in results if res.get("msg") == "抢购成功！")
    fail_count = sum(1 for res in results if res.get("msg") == "库存不足，抢购失败")

    # 1. 验证：5 个人抢 1 件商品，绝对只能有 1 个人成功！
    assert success_count == 1, f"严重超卖漏洞！预期 1 人成功，实际成功了 {success_count} 人"
    
    # 2. 验证：剩下的 4 个人必须是被拦截的失败状态
    assert fail_count == 4, f"并发拦截异常！预期 4 人失败，实际失败了 {fail_count} 人"
    
    # 3. 验证：兜底查询最终库存，必须是 0
    final_stock_res = requests.get(f"{BASE_URL}/inventory/{target_sku}")
    assert final_stock_res.json()["remain_stock"] == 0, "库存扣减异常，不为 0"