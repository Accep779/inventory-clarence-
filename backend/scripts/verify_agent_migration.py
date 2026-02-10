import asyncio
import sys
from httpx import AsyncClient, ASGITransport
# Add parent dir to path to find app
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app

async def test_agent(name, client_id, client_secret, valid_scope_check, invalid_endpoint, invalid_payload):
    print(f"\n--- Testing {name} ---")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Auth
        print(f"Authenticating {client_id}...")
        resp = await client.post("/internal/agents/auth", json={
            "client_id": client_id, "client_secret": client_secret
        })
        if resp.status_code != 200:
            print(f"❌ Auth Failed: {resp.text}")
            return False
            
        token = resp.json()['access_token']
        print(f"✅ Authenticated. Token acquired.")
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Check Scopes (/me)
        resp = await client.get("/internal/agents/me", headers=headers)
        me = resp.json()
        print(f"Identity: {me}")
        scopes = me.get('scopes', [])
        if valid_scope_check not in scopes:
             print(f"❌ Missing expected scope: {valid_scope_check}")
             return False
        print(f"✅ Scope '{valid_scope_check}' present.")
        
        # 3. Security (Strict Enforcement) - Try forbidden action
        print(f"Attempting Forbidden Action: {invalid_endpoint}...")
        resp = await client.post(f"/internal/agents/{invalid_endpoint}", json=invalid_payload, headers=headers)
        
        if resp.status_code == 403:
            print("✅ Strict Enforcement Active (403 Forbidden received).")
        else:
            print(f"❌ Strict Enforcement FAILED. Status: {resp.status_code} Response: {resp.text}")
            return False
            
    return True

async def main():
    print("Beginning Agent Migration Verification (Direct App Test)...")
    
    # Test Matchmaker
    match_ok = await test_agent(
        "Matchmaker", 
        "agent_matchmaker_match_v1", 
        "secret_match_123", 
        "matchmaker:update", 
        "inventory/status", # Should fail (Observer only)
        {"updates": []} # Valid payload structure for inventory/status
    )
    
    
    if match_ok:
        print("\n🎉 MATCHMAKER SYSTEM SECURE. STRICT ENFORCEMENT VERIFIED.")
    else:
        print("\n❌ VERIFICATION FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
