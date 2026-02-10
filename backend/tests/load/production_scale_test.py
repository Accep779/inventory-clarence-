import random
import uuid
import time
from locust import HttpUser, task, between
from jose import jwt

# Configuration
SECRET_KEY = "demo-secret-key-12345"  # Must match backend env
LOAD_TEST_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "cephly.loadtest")

class MerchantUser(HttpUser):
    wait_time = between(1, 5)  # Realistic think time between actions
    
    def on_start(self):
        """
        Simulate merchant login using pre-seeded data.
        Picks one of the 100 seeded merchants at random.
        """
        # 1. Identity & Auth
        self.merchant_idx = random.randint(0, 99)
        self.merchant_id = str(uuid.uuid5(LOAD_TEST_NAMESPACE, f"merchant-{self.merchant_idx}"))
        self.token = self._generate_token(self.merchant_id)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # 2. Known Data (Deterministic)
        # We know the product ID because we seeded it deterministically
        self.product_id = str(uuid.uuid5(LOAD_TEST_NAMESPACE, f"product-{self.merchant_idx}"))
        
    def _generate_token(self, merchant_id):
        payload = {
            "sub": merchant_id,
            "exp": int(time.time()) + 3600
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    @task(4)
    def view_dashboard(self):
        """Simulate viewing the main dashboard (Inbox + Products)."""
        # Inbox is the main landing
        with self.client.get("/api/inbox", headers=self.headers, name="/api/inbox", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Failed to load inbox: {response.text}")
        
        # Products widget
        with self.client.get("/api/products?limit=10", headers=self.headers, name="/api/products", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Failed to load products: {response.text}")

    @task(3)
    def trigger_analysis(self):
        """Trigger strategy analysis for a product."""
        # Using pre-seeded product ID
        payload = {"product_id": self.product_id}
        with self.client.post("/api/strategy/plan", json=payload, headers=self.headers, name="/api/strategy/plan", catch_response=True) as response:
            if response.status_code == 200:
                pass
            elif response.status_code == 400 and "already" in response.text.lower():
                # If plan already exists or analyzing, that's fine for load test noise
                response.success()
            else:
                msg = f"Analysis failed: {response.status_code} - {response.text[:200]}"
                print(msg)
                response.failure(msg)

    @task(2)
    def approve_proposal(self):
        """Find a pending proposal and approve it."""
        # 1. List pending items
        pending_items = []
        with self.client.get("/api/inbox?status=pending", headers=self.headers, name="/api/inbox?status=pending", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                pending_items = data.get("items", [])
            else:
                msg = f"Failed to list proposals: {response.status_code} - {response.text[:200]}"
                print(msg)
                response.failure(msg)
                return
        
        # 2. Approve one if exists
        if pending_items:
            item_id = pending_items[0]["id"]
            # To avoid running out of items, maybe we act like we approved but don't commit? 
            # Or we let it burn down the queue.
            # For a 30 min test, we'd run out of pending items if we only seeded 1 per merchant.
            # Ideally the "Analysis" task generates new proposals!
            # So the loop is: Analyze -> Creates Proposal -> Approve -> Done.
            # Since we have "Trigger Analysis" task (30%), it should feed the "Approve" task (20%).
            with self.client.post(f"/api/inbox/{item_id}/approve", headers=self.headers, name="/api/inbox/{id}/approve", catch_response=True) as response:
                if response.status_code == 200:
                    pass
                elif response.status_code == 404:
                    # Race condition or already approved
                    response.success()
                else:
                    msg = f"Approval failed: {response.status_code} - {response.text[:200]}"
                    print(msg)
                    response.failure(msg)

    @task(1)
    def view_campaigns(self):
        """View the marketing campaigns page."""
        with self.client.get("/api/campaigns", headers=self.headers, name="/api/campaigns", catch_response=True) as response:
             if response.status_code != 200:
                msg = f"Failed to load campaigns: {response.status_code} - {response.text[:200]}"
                print(msg)
                response.failure(msg)
