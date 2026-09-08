import pytest
import requests
from .utils import read_yaml_data
from .schemas import ReqresUserSchema
from pydantic import ValidationError

class TestReqresAPI:
    @pytest.mark.parametrize("case_data", read_yaml_data("reqres_users.yaml"))
    def test_get_user(self, case_data):
        # 1. 解包 YAML 数据
        user_id = case_data["user_id"]
        expected_status = case_data["expected_status"]
        expected_name = case_data["expected_first_name"]
        
        # 2. 请求外网真实接口
        resp = requests.get(f"https://reqres.in/api/users/{user_id}")
        
        # 3. 基础状态码断言
        assert resp.status_code == expected_status
        
        # 4. 核心业务断言分流
        if expected_status == 200:
            # 200时，必须完全符合嵌套 schema
            try:
                parsed_resp = ReqresUserSchema(**resp.json())
            except ValidationError as e:
                pytest.fail(f"外网接口结构突变: {e}")
                
            # 验证具体的业务字段是否正确
            assert parsed_resp.data.first_name == expected_name
        else:
            # 404时，按照官方文档，接口应返回空字典 {}
            assert resp.json() == {}