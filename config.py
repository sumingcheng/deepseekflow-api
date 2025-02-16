import os


class Config:
    # API 配置
    UPSTREAM_API_URL = os.getenv('UPSTREAM_API_URL', 'http://127.0.0.1:8000/v1/chat/completions')
    TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', '120'))
    PORT = int(os.getenv('PORT', '8080'))
    
    # 必需的环境变量检查
    required_vars = ['UPSTREAM_API_URL']
    for var in required_vars:
        if locals()[var] is None:
            raise ValueError(f"Environment variable {var} is not set")

    @classmethod
    def as_dict(cls):
        return {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith('__') and not callable(v)
        }
