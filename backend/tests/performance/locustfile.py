from locust import HttpUser, task, between
import uuid
import time
from jose import jwt

# Use the same secret as in dev/test environment
SECRET_KEY = "demo-secret-key-12345"
TEST_MERCHANT_ID = "test-merchant-123"

class CephlyLoadTester(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        """Setup test data/auth for the user."""
        self.merchant_id = TEST_MERCHANT_ID
        # Generate a valid JWT token
        payload = {
            "sub": self.merchant_id,
            "exp": int(time.time()) + 3600
        }
        self.auth_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    @task(3)
    def check_health(self):
        self.client.get("/health")
    
    @task(2)
    def view_inbox(self):
        self.client.get("/api/inbox", headers={"Authorization": f"Bearer {self.auth_token}"})
    
    @task(1)
    def simulate_webhook(self):
        payload = {
            "id": 12345,
            "title": "Load Test Product",
            "variants": [{"price": "19.99", "inventory_quantity": 100}]
        }
        headers = {
            "X-Shopify-Hmac-SHA256": "dummy",
            "X-Shopify-Shop-Domain": "load-test.myshopify.com",
            "X-Shopify-Topic": "products/update"
        }
        self.client.post("/api/webhooks/products", json=payload, headers=headers)
