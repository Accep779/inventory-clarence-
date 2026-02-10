"""
Internal API Router for Autonomous Agents.
This API is NOT exposed to the public internet. It is for internal agent-to-system communication only.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.auth_middleware import get_current_agent, create_agent_token
from app.services.identity import IdentityService
from app.models import InboxItem

router = APIRouter(
    prefix="/internal/agents",
    tags=["internal-agents"],
    responses={404: {"description": "Not found"}},
)

# -----------------------------------------------------------------------------
# 1. AGENT AUTHENTICATION (The "Login" Endpoint)
# -----------------------------------------------------------------------------

class AgentLoginRequest(BaseModel):
    client_id: str
    client_secret: str

class AgentTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

@router.post("/auth", response_model=AgentTokenResponse)
async def authenticate_agent(
    request: AgentLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Exchange Client Credentials for an Agent Access Token.
    """
    # 1. Verify Client ID belongs to a merchant
    # Ideally we'd need to know *which* merchant, but client_id is unique globally in our schema
    from sqlalchemy import select
    from app.models import AgentClient
    
    result = await db.execute(select(AgentClient).where(AgentClient.client_id == request.client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=401, detail="Invalid Client ID")
        
    # 2. Use Identity Service to verify secret
    identity_service = IdentityService(db, client.merchant_id)
    agent_ctx = await identity_service.authenticate_agent(request.client_id, request.client_secret)
    
    if not agent_ctx:
        raise HTTPException(status_code=401, detail="Invalid Client Secret")
        
    # 3. Mint Token
    token_data = {
        "client_id": agent_ctx.client_id,
        "agent_type": agent_ctx.agent_type,
        "merchant_id": agent_ctx.merchant_id,
        "scopes": client.allowed_scopes
    }
    
    token = create_agent_token(token_data)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600 # 1 hour
    }


# -----------------------------------------------------------------------------
# 2. PROTECTED RESOURCES (Requires Agent Token)
# -----------------------------------------------------------------------------

@router.get("/me")
async def get_agent_identity(current_agent: dict = Depends(get_current_agent)):
    """Self-inspection endpoint for agents."""
    return {
        "identity": f"Agent {current_agent['agent_type']}",
        "scopes": current_agent['scopes'],
        "merchant_id": current_agent['merchant_id']
    }

class ProposalCreateRequest(BaseModel):
    title: str
    description: str
    pricing: dict
    strategy: str
    discount_percent: float = 0.0
    projected_revenue: float = 0.0
    copy_data: dict = {}
    reasoning: dict = {}

@router.post("/proposals")
async def create_proposal(
    proposal: ProposalCreateRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure proposal creation.
    Enforces that only agents with 'proposals:write' scope can create proposals.
    """
    # SCOPE CHECK
    if "proposals:write" not in current_agent.get("scopes", []):
        raise HTTPException(status_code=403, detail="Missing required scope: proposals:write")
        
    # Create proposal linked to this specific agent execution
    new_item = InboxItem(
        merchant_id=current_agent['merchant_id'],
        type="clearance_proposal",
        status="pending",
        proposal_data=proposal.dict(),
        agent_type=current_agent['agent_type'],
        risk_level="moderate", # This would be dynamic in production
        discount_percent=proposal.discount_percent,
        projected_revenue=proposal.projected_revenue,
        strategy=proposal.strategy,
        copy_data=proposal.copy_data,
        reasoning=proposal.reasoning
    )
    
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)
    
    return {"status": "created", "id": new_item.id}


# -----------------------------------------------------------------------------
# 3. CAMPAIGN EXECUTION CONTROL (Execution Agent Only)
# -----------------------------------------------------------------------------

class ExecutionLockRequest(BaseModel):
    proposal_id: str

@router.post("/campaigns/lock")
async def lock_campaign_execution(
    request: ExecutionLockRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Atomic Claim: Execution Agent requests permission to run this proposal.
    Requires 'campaigns:execute' scope.
    """
    if "campaigns:execute" not in current_agent.get("scopes", []):
         raise HTTPException(status_code=403, detail="Missing scope: campaigns:execute")
    
    from sqlalchemy import update, select
    
    # Atomic status update: pending/approved -> executing
    result = await db.execute(
        update(InboxItem)
        .where(
            InboxItem.id == request.proposal_id,
            InboxItem.merchant_id == current_agent['merchant_id'],
            InboxItem.status.in_(['approved', 'pending'])
        )
        .values(status='executing', agent_type=current_agent['agent_type']) # Audit who claimed it
        .returning(InboxItem)
    )
    
    proposal = result.scalar_one_or_none()
    
    if not proposal:
        # Check if already done
        check = await db.execute(select(InboxItem).where(InboxItem.id == request.proposal_id))
        existing = check.scalar_one_or_none()
        if existing:
            return {"status": "error", "reason": f"Proposal already in status: {existing.status}"}
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    await db.commit()
    return {"status": "locked", "proposal": proposal.proposal_data, "origin_id": proposal.origin_execution_id}

class ExecutionResultRequest(BaseModel):
    proposal_id: str
    status: str # executed, failed
    details: dict

@router.post("/campaigns/complete")
async def complete_campaign_execution(
    request: ExecutionResultRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Report execution result.
    """
    from sqlalchemy import update
    from datetime import datetime
    
    await db.execute(
        update(InboxItem)
        .where(
            InboxItem.id == request.proposal_id,
            InboxItem.merchant_id == current_agent['merchant_id']
        )
        .values(
            status=request.status, 
            server_created_at=(datetime.utcnow() if request.status == 'executed' else None), # abusing column for executed_at timestamp
            proposal_data=request.details # Update with result details requires merging in real app, simplistic replace here
        )
    )
    await db.commit()
    return {"status": "updated"}


class CampaignCreateRequest(BaseModel):
    name: str
    type: str
    product_ids: list[str]
    target_segments: list[str]
    content_snapshot: dict
    origin_execution_id: str = None
    status: str = 'active'

@router.post("/campaigns/create")
async def create_campaign(
    request: CampaignCreateRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new campaign record.
    Requires 'campaigns:execute' scope.
    """
    if "campaigns:execute" not in current_agent.get("scopes", []):
         raise HTTPException(status_code=403, detail="Missing scope: campaigns:execute")
    
    from app.models import Campaign
    from datetime import datetime
    
    campaign = Campaign(
        merchant_id=current_agent['merchant_id'],
        name=request.name,
        type=request.type,
        status=request.status,
        product_ids=request.product_ids,
        target_segments=request.target_segments,
        content_snapshot=request.content_snapshot,
        origin_execution_id=request.origin_execution_id,
        created_at=datetime.utcnow()
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    
    return {"status": "created", "id": campaign.id}

class TouchLogRequest(BaseModel):
    campaign_id: str
    channel: str
    external_id: str
    status: str
    customer_id: str = None

@router.post("/campaigns/log")
async def log_campaign_touch(
    request: TouchLogRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Log an execution touch (email/sms sent).
    Requires 'campaigns:execute' scope.
    """
    if "campaigns:execute" not in current_agent.get("scopes", []):
         raise HTTPException(status_code=403, detail="Missing scope: campaigns:execute")

    from app.models import TouchLog
    
    log = TouchLog(
        merchant_id=current_agent['merchant_id'],
        campaign_id=request.campaign_id,
        channel=request.channel,
        external_id=request.external_id,
        status=request.status,
        customer_id=request.customer_id
    )
    db.add(log)
    await db.commit()
    return {"status": "logged"}

class FailureNotificationRequest(BaseModel):
    reason: str
    details: str

@router.post("/notifications/failure")
async def notify_failure(
    request: FailureNotificationRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Notify merchant of execution failure.
    """
    new_item = InboxItem(
        merchant_id=current_agent['merchant_id'],
        type="campaign_failure",
        status="pending",
        proposal_data={"message": f"Execution failed: {request.reason}", "details": request.details},
        agent_type=current_agent['agent_type'],
        risk_level="high"
    )
    db.add(new_item)
    await db.commit()
    return {"status": "notified"}

class ThoughtLogRequest(BaseModel):
    agent_type: str
    thought_type: str
    summary: str
    detailed_reasoning: dict = {}
    confidence_score: float = 1.0
    step_number: int = 1
    execution_id: str = None
    product_id: str = None

@router.post("/thoughts")
async def log_agent_thought(
    request: ThoughtLogRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Log an agent's internal monologue securely.
    """
    from app.services.thought_logger import ThoughtLogger
    from decimal import Decimal
    
    # Allow all authenticated agents to log thoughts
    # No specific scope check beyond basic auth, or maybe 'thoughts:write' if strict
    
    await ThoughtLogger.log_thought(
        merchant_id=current_agent['merchant_id'],
        agent_type=current_agent['agent_type'], # Enforce identity
        thought_type=request.thought_type,
        summary=request.summary,
        detailed_reasoning=request.detailed_reasoning,
        execution_id=request.execution_id,
        confidence_score=request.confidence_score,
        step_number=request.step_number,
        product_id=request.product_id
    )
    return {"status": "logged"}


# -----------------------------------------------------------------------------
# 4. INVENTORY OBSERVATION (Observer Agent Only)
# -----------------------------------------------------------------------------

class ProductStatusUpdate(BaseModel):
    product_id: str
    is_dead_stock: bool
    dead_stock_severity: str
    velocity_score: float
    days_since_last_sale: int

class BulkInventoryUpdateRequest(BaseModel):
    updates: list[ProductStatusUpdate]

@router.post("/inventory/status")
async def update_inventory_status(
    request: BulkInventoryUpdateRequest,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update product risk status.
    Requires 'inventory:update' scope.
    """
    if "inventory:update" not in current_agent.get("scopes", []):
         raise HTTPException(status_code=403, detail="Missing scope: inventory:update")
    
    from sqlalchemy import update
    from app.models import Product
    
    count = 0
    # Process updates in a single transaction
    # Since SQLAlchemy doesn't support bulk update with different values easily in async without raw SQL or case/when,
    # we'll loop for now. For 500 items/batch it's acceptable for this scale.
    # Optimization: Use mappings or raw SQL if slow.
    
    for item in request.updates:
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id, Product.merchant_id == current_agent['merchant_id'])
            .values(
                is_dead_stock=item.is_dead_stock,
                dead_stock_severity=item.dead_stock_severity,
                velocity_score=item.velocity_score,
                days_since_last_sale=item.days_since_last_sale,
                updated_at=func.now()
            )
        )
        count += 1
        
    await db.commit()
    return {"status": "success", "updated_count": count}


# -----------------------------------------------------------------------------
# 5. MATCHMAKER AGENT (Connectors)
# -----------------------------------------------------------------------------

class SegmentStatsUpdate(BaseModel):
    segment_counts: dict
    reasoning: str

@router.post("/matchmaker/segments")
async def update_segment_stats(
    update: SegmentStatsUpdate,
    current_agent: dict = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Matchmaker reporting segment analysis.
    Requires 'matchmaker:update' scope.
    """
    if "matchmaker:update" not in current_agent.get("scopes", []):
         raise HTTPException(status_code=403, detail="Missing scope: matchmaker:update")

    # In a real system, we would store this in a 'SegmentHistory' table.
    # For now, we'll log it as an agent thought to maintain visibility.
    from app.services.thought_logger import ThoughtLogger
    
    await ThoughtLogger.log_thought(
        merchant_id=current_agent['merchant_id'],
        agent_type="matchmaker",
        thought_type="market_analysis",
        summary=f"Segment analysis updated. Active counts: {update.segment_counts}",
        detailed_reasoning={"counts": update.segment_counts, "reasoning": update.reasoning}
    )
    
    return {"status": "recorded"}



