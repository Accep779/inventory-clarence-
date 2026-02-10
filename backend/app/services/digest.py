from datetime import datetime
from sqlalchemy import select, delete
from app.database import async_session_maker
from app.models import PendingNotification
from app.services.gateway import GatewayService

class DigestService:
    """
    Manages the 'Anti-Fatigue' Layer.
    Batches low-priority notifications and delivers them as a summary.
    """
    
    async def add_notification(self, merchant_id: str, content: str, priority: str = "low", topic: str = "general"):
        """
        Queue a notification for later delivery.
        """
        async with async_session_maker() as session:
            note = PendingNotification(
                merchant_id=merchant_id,
                content=content,
                priority=priority,
                topic=topic
            )
            session.add(note)
            await session.commit()
            print(f"📥 [Digest] Queued '{topic}' notification for {merchant_id}")

    async def flush_digest(self, merchant_id: str, channel: str = "email:user@example.com"):
        """
        Deliver all pending notifications as a single summary.
        """
        gateway = GatewayService()
        
        async with async_session_maker() as session:
            # 1. Fetch pending
            stmt = select(PendingNotification).where(
                PendingNotification.merchant_id == merchant_id
            ).order_by(PendingNotification.created_at)
            
            notes = (await session.execute(stmt)).scalars().all()
            
            if not notes:
                print(f"📭 [Digest] No pending notifications to flush.")
                return 0
            
            # 2. Build Summary
            count = len(notes)
            summary_lines = [f"📅 Daily Briefing ({count} items):"]
            for note in notes:
                summary_lines.append(f"- [{note.topic}] {note.content}")
            
            full_content = "\n".join(summary_lines)
            
            # 3. Send via Gateway
            print(f"🚚 [Digest] Flushing {count} items to {channel}")
            await gateway.send_message(channel, full_content)
            
            # 4. Cleanup
            delete_stmt = delete(PendingNotification).where(
                PendingNotification.id.in_([n.id for n in notes])
            )
            await session.execute(delete_stmt)
            await session.commit()
            
            return count
