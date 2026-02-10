# from slowapi import Limiter
# from slowapi.util import get_remote_address
from fastapi import Request

# MOCK LIMITER to bypass import errors in dev
class Limiter:
    def __init__(self, key_func=None):
        pass
    def limit(self, limit_value):
        def decorator(func):
            return func
        return decorator

def get_remote_address(request):
    return "127.0.0.1"

def get_rate_limit_key(request: Request):
    return "test"

limiter = Limiter(key_func=get_rate_limit_key)
