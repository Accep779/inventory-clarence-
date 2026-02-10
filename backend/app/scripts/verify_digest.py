import asyncio
import os
import sys

# Ensure backend acts as root
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.gateway import GatewayService
from app.services.digest import DigestService
from app.database import async_session_maker
from app.models import PendingNotification
from sqlalchemy import delete

async def main():
    print("🌅 Testing Digest Manager (Anti-Fatigue)...")
    merchant_id = "test_merchant_digest"
    
    # 0. Cleanup from previous runs
    async with async_session_maker() as session:
        await session.execute(delete(PendingNotification).where(PendingNotification.merchant_id == merchant_id))
        await session.commit()
    
    gateway = GatewayService()
    digest = DigestService()
    
    # 1. Send LOW Priority Messages (Should be Intercepted)
    print("\n[1] Sending Low Priority Messages...")
    res1 = await gateway.send_message("email:bob@co.com", "Spam 1", priority="low", merchant_id=merchant_id, topic="Marketing")
    res2 = await gateway.send_message("email:bob@co.com", "Spam 2", priority="low", merchant_id=merchant_id, topic="Inventory")
    res3 = await gateway.send_message("email:bob@co.com", "Important!", priority="normal", merchant_id=merchant_id) # Should go through
    
    if res1 == "queued_for_digest" and res2 == "queued_for_digest":
        print("   ✅ Low priority messages Queued.")
    else:
        print(f"   ❌ Fail: Low priority not queued. Got: {res1}, {res2}")
        return

    # 2. Verify Database State
    print("\n[2] Checking Database...")
    async with async_session_maker() as session:
        from sqlalchemy import select, func
        count = (await session.execute(
            select(func.count(PendingNotification.id)).where(PendingNotification.merchant_id == merchant_id)
        )).scalar()
        
    if count == 2:
        print(f"   ✅ Database has 2 pending items.")
    else:
        print(f"   ❌ Fail: Database has {count} items (Expected 2).")
        return

    # 3. Flush Digest (Should send 1 aggregate email)
    print("\n[3] Flushing Digest...")
    flushed_count = await digest.flush_digest(merchant_id, channel="terminal:bob_digest")
    
    if flushed_count == 2:
        print(f"   ✅ Flushed 2 items to 'terminal:bob_digest'.")
    else:
        print(f"   ❌ Fail: Flushed {flushed_count} items.")

if __name__ == "__main__":
    asyncio.run(main())
