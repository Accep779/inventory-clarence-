from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InboxItem, AuditLog, Merchant
from app.services.identity import AgentContext
import logging
import json
from redis.asyncio import from_url
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

class InboxService:
    """
    Core service for the HITL Decision Inbox.
    Handles tenant isolation, audit logging, and batch validation.
    """
    
    def __init__(self, db: AsyncSession, merchant_id: str):
        self.db = db
        self.merchant_id = merchant_id

    async def _log_action(self, action: str, entity_type: str, entity_id: str, metadata: Optional[dict] = None, execution_id: Optional[str] = None, actor: Optional['AgentContext'] = None):
        """Create an audit log entry with forensic linkage."""
        
        # Determine actor details
        actor_type = "system"
        client_id = None
        actor_agent_type = None
        
        if actor:
            actor_type = "agent"
            client_id = actor.client_id
            actor_agent_type = actor.agent_type
            
        log = AuditLog(
            merchant_id=self.merchant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            execution_id=execution_id,
            actor_type=actor_type,
            client_id=client_id,
            actor_agent_type=actor_agent_type
        )
        self.db.add(log)
        await self.db.flush()

    async def notify_update(self, item_id: str, action: str):
        """Broadcast an update message via Redis for SSE clients."""
        try:
            redis = await from_url(settings.REDIS_URL, decode_responses=True)
            channel = f"inbox_updates:{self.merchant_id}"
            message = json.dumps({
                "item_id": item_id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat()
            })
            await redis.publish(channel, message)
            await redis.close()
            logger.info(f"📣 Broadcasted {action} for item {item_id} on channel {channel}")
        except Exception as e:
            logger.error(f"Failed to broadcast update: {e}")

    async def list_proposals(self, status: Optional[str] = None, limit: int = 50, offset: int = 0):
        """Fetch proposals for the current merchant with tenant isolation."""
        from app.models import AsyncAuthorizationRequest
        
        # Outer join to get CIBA status
        query = (
            select(InboxItem, AsyncAuthorizationRequest)
            .outerjoin(AsyncAuthorizationRequest, InboxItem.id == AsyncAuthorizationRequest.inbox_item_id)
            .where(InboxItem.merchant_id == self.merchant_id)
        )
        
        if status:
            query = query.where(InboxItem.status == status)
        
        query = query.order_by(desc(InboxItem.created_at)).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        items = []
        for item, auth_req in rows:
            # Attach CIBA status to the item object for the Pydantic model
            if auth_req:
                item.waiting_for_mobile_auth = (auth_req.status == 'pending')
                item.mobile_auth_status = auth_req.status
            else:
                item.waiting_for_mobile_auth = False
                item.mobile_auth_status = None
            items.append(item)
        
        # Get pending count for badge
        pending_query = select(InboxItem).where(
            InboxItem.merchant_id == self.merchant_id,
            InboxItem.status == "pending"
        )
        pending_result = await self.db.execute(pending_query)
        pending_count = len(pending_result.scalars().all())
        
        return items, pending_count

    async def get_proposal(self, item_id: str):
        """Fetch a specific proposal and log the view action."""
        query = select(InboxItem).where(
            InboxItem.id == item_id,
            InboxItem.merchant_id == self.merchant_id
        )
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()
        
        if item:
            if not item.viewed_at:
                item.viewed_at = datetime.utcnow()
                await self._log_action("View", "InboxItem", item_id)
                await self.db.commit()
                
        return item

    async def approve_proposal(self, item_id: str):
        """Validate and approve a proposal."""
        item = await self.get_proposal(item_id)
        if not item:
            return None, "Proposal not found"
        
        # [SECURITY HARDENING] Double-check merchant_id alignment
        if item.merchant_id != self.merchant_id:
             logger.critical(f"🛑 SECURITY ALERT: Tenant {self.merchant_id} attempted to access {item_id} belonging to {item.merchant_id}")
             return None, "Proposal not found"
        
        if item.status != "pending":
            return None, f"Cannot approve proposal in status: {item.status}"

        # Batch Validation Logic
        items = item.proposal_data.get("items", [])
        if len(items) > 100:
             return None, "Batch exceeds safety limit of 100 items."
             
        total_value = sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in items)
        if total_value > 50000:
             return None, "Batch total value exceeds $50,000 threshold. Manual review required."

        item.status = "approved"
        item.decided_at = datetime.utcnow()
        
        # Unlock linked CIBA request
        await self._unlock_ciba_request(item_id, "approved")
        
        await self._log_action("Approve", "InboxItem", item_id, {"item_count": len(items), "total_value": total_value})
        await self.db.commit()
        
        # Real-time update
        await self.notify_update(item_id, "approved")
        
        return item, None

    async def reject_proposal(self, item_id: str, reason: Optional[str] = None):
        """Reject a proposal with an optional reason."""
        item = await self.get_proposal(item_id)
        if not item:
            return None, "Proposal not found"

        # [SECURITY HARDENING] Double-check merchant_id alignment
        if item.merchant_id != self.merchant_id:
             logger.critical(f"🛑 SECURITY ALERT: Tenant {self.merchant_id} attempted to access {item_id} belonging to {item.merchant_id}")
             return None, "Proposal not found"

        item.status = "rejected"
        item.decided_at = datetime.utcnow()
        
        if reason:
            if not item.proposal_data:
                item.proposal_data = {}
            item.proposal_data["rejection_reason"] = reason

        # Unlock linked CIBA request
        await self._unlock_ciba_request(item_id, "rejected", "dashboard")

        await self._log_action("Reject", "InboxItem", item_id, {"reason": reason})
        await self.db.commit()
        
        # Real-time update
        await self.notify_update(item_id, "rejected")
        
        return item, None

    async def _unlock_ciba_request(self, inbox_item_id: str, decision: str, channel: str = "dashboard"):
        """
        Unlock any pending CIBA request linked to this inbox item.
        This handles the case where a user manually approves via Dashboard
        instead of the mobile app, ensuring the Agent gets unblocked.
        """
        from app.services.ciba_service import CIBAService
        
        # We need to find if there is an active auth request for this item
        # Since we don't have the auth_req_id here, we query for it
        from app.models import AsyncAuthorizationRequest
        
        result = await self.db.execute(
            select(AsyncAuthorizationRequest).where(
                AsyncAuthorizationRequest.inbox_item_id == inbox_item_id,
                AsyncAuthorizationRequest.status.in_(["pending", "pending_manual"])
            )
        )
        auth_req = result.scalar_one_or_none()
        
        if auth_req:
            # We found a pending request - process it via CIBAService
            # to trigger all the Redis pub/sub logic
            ciba = CIBAService(self.merchant_id)
            await ciba.process_decision(auth_req.auth_req_id, decision, channel)
            logger.info(f"🔓 CIBA request {auth_req.auth_req_id} unlocked via Dashboard action")

    async def remove_item_from_batch(self, item_id: str, sku: str):
        """Remove a specific SKU from a batch proposal before approval."""
        item = await self.get_proposal(item_id)
        if not item or item.status != "pending":
            return None, "Proposal not found or not in pending state"

        original_items = item.proposal_data.get("items", [])
        new_items = [i for i in original_items if i.get("sku") != sku]
        
        if len(new_items) == len(original_items):
            return None, f"SKU {sku} not found in proposal"

        item.proposal_data["items"] = new_items
        # Force SQLAlchemy to recognize the JSON change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(item, "proposal_data")
        
        await self._log_action("Edit", "InboxItem", item_id, {"removed_sku": sku})
        await self.db.commit()
        
        return item, None



    async def chat_with_agent(self, item_id: str, message: str):
        """Interact with the agent about a specific proposal."""
        item = await self.get_proposal(item_id)
        if not item:
            return None, "Proposal not found"
            
        # 1. Update history with user message
        if not item.chat_history:
            item.chat_history = []
            
        # Clone list to force SQLAlchemy dirty check
        history = list(item.chat_history)
        history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        item.chat_history = history
        await self.db.flush()
        
        # 2. Call LLM for response
        from app.services.llm_router import LLMRouter
        router = LLMRouter()
        
        system_prompt = f"""
        You are an intelligent retail agent named '{item.agent_type.title()} Agent'.
        You created a proposal titled '{item.proposal_data.get('title', 'Strategy')}'.
        
        CONTEXT:
        {json.dumps(item.proposal_data, indent=2)}
        
        GOAL:
        Help the user refine this proposal. You can explain your reasoning, adjust parameters (like discount %), 
        or rewrite the copy.
        
        If the user asks to change something (e.g. "change discount to 20%"), 
        you should acknowledge it and provide the UPDATED JSON parameters in a specific block.
        
        RESPONSE FORMAT:
        Return a JSON object with:
        - "response": Your conversational reply to the user.
        - "updated_proposal_data": (Optional) Any fields in the proposal_data that should be changed.
        
        Example:
        {{
            "response": "I've updated the discount to 20% as requested.",
            "updated_proposal_data": {{ "pricing": {{ "discount_percent": 20 }} }}
        }}
        """
        
        try:
            llm_result = await router.complete(
                task_type="agent_chat",
                system_prompt=system_prompt,
                user_prompt=message,
                merchant_id=self.merchant_id,
                metadata={"item_id": item_id}
            )
            
            # Parse response
            try:
                response_data = json.loads(llm_result['content'])
                agent_reply = response_data.get("response", "I processed your request.")
                updates = response_data.get("updated_proposal_data", {})
            except json.JSONDecodeError:
                # Fallback if LLM returns raw text
                agent_reply = llm_result['content']
                updates = {}
                
            # 3. Apply updates if any
            if updates and isinstance(updates, dict):
                # Deep merge would be better, but shallow update for now
                current_data = dict(item.proposal_data)
                current_data.update(updates)
                item.proposal_data = current_data
                
            # 4. Append agent response to history
            history.append({
                "role": "assistant",
                "content": agent_reply,
                "timestamp": datetime.utcnow().isoformat()
            })
            item.chat_history = history
            
            await self._log_action("AgentChat", "InboxItem", item_id, metadata={"message": message})
            await self.db.commit()
            
            # Notify frontend
            await self.notify_update(item_id, "chat_message")
            
            return {
                "history": history,
                "updated_proposal": item.proposal_data
            }, None
            
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return None, f"Agent is currently unavailable: {str(e)}"
        proposal = InboxItem(
            merchant_id=self.merchant_id,
            type=proposal_type,
            agent_type=agent_type,
            status='pending',
            proposal_data=proposal_data,
            risk_level=risk_level,
            confidence=confidence,
            origin_execution_id=origin_execution_id
        )
        self.db.add(proposal)
        await self.db.flush()
        
        # Broadcast the new item
        await self.notify_update(proposal.id, "created")
        
        return proposal

    async def chat_with_agent(self, item_id: str, message: str):
        """
        Process a user message, get agent response, and potentially update the proposal.
        """
        from app.services.llm_router import LLMRouter
        
        item = await self.get_proposal(item_id)
        if not item:
            return None, "Proposal not found"
            
        if item.status != "pending":
            return None, "Can only chat with pending proposals."
            
        # 1. Update History (User)
        if not item.chat_history:
            item.chat_history = []
            
        # Append to SQLAlchemy-tracked JSON
        history = list(item.chat_history)
        history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        item.chat_history = history # Re-assign to trigger dirty flag
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(item, "chat_history")
        
        # 2. Call Agent via LLM Router
        router = LLMRouter()
        
        # Build Context
        context = f"""
        CURRENT PROPOSAL:
        {json.dumps(item.proposal_data, indent=2)}
        
        CHAT HISTORY:
        {json.dumps(history[:-1], indent=2)}
        
        USER MESSAGE:
        {message}
        """
        
        system_prompt = f"""You are the {item.agent_type} Agent. 
        You created this proposal. The user is asking for changes or explanation.
        
        You have helper tools to UPDATE the proposal JSON directly if requested.
        
        Response Format (JSON):
        {{
            "response": "Text reply to user explaining what you did or answering question",
            "updated_proposal_data": {{Key-Value pairs to MERGE into proposal_data}}
        }}
        
        Example: User says "Make discount 50%" -> 
        {{
            "response": "I've increased the discount to 50% as requested. This will lower margin to 5%.",
            "updated_proposal_data": {{ "pricing": {{ "discount_percent": 50, "sale_price": ... }} }}
        }}
        
        If no changes needed, keep "updated_proposal_data" empty.
        Valid keys for updates: pricing, copy, audience, strategy.
        Encryption/ID fields cannot be changed.
        """
        
        try:
            res = await router.complete(
                task_type='agent_chat',
                system_prompt=system_prompt,
                user_prompt=context,
                merchant_id=self.merchant_id
            )
            
            # 3. Parse Response
            raw_content = res['content'].strip()
            if raw_content.startswith("```"): 
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"): raw_content = raw_content[4:]
            
            try:
                agent_action = json.loads(raw_content)
                text_response = agent_action.get("response", "Proposal updated.")
                updates = agent_action.get("updated_proposal_data", {})
            except json.JSONDecodeError:
                # Fallback implementation if LLM returns text
                text_response = raw_content
                updates = {}
                
            # 4. Apply Updates
            if updates and isinstance(updates, dict):
                # Deep merge or top-level update? For safety, top-level merge
                for k, v in updates.items():
                    if k in item.proposal_data:
                        if isinstance(item.proposal_data[k], dict) and isinstance(v, dict):
                            item.proposal_data[k].update(v)
                        else:
                            item.proposal_data[k] = v
                flag_modified(item, "proposal_data")
                
            # 5. Update History (Agent)
            history = list(item.chat_history)
            history.append({
                "role": "agent",
                "content": text_response,
                "timestamp": datetime.utcnow().isoformat()
            })
            item.chat_history = history
            flag_modified(item, "chat_history")
            
            await self._log_action("Chat", "InboxItem", item_id)
            await self.db.commit()
            
            # Broadcast
            await self.notify_update(item_id, "chat_activity")
            
            return item, None
            
        except Exception as e:
            logger.error(f"Agent chat failed: {e}")
            return None, "Agent is temporarily offline."
