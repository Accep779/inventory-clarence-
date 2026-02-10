"""
CIBA Authorization Router
=========================

API endpoints for merchant authorization decisions.
Mobile/dashboard endpoints to authorize or reject CIBA requests.
"""

import logging
from typing import Literal, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.ciba_service import CIBAService
from app.models import Merchant
from app.routers.dependencies import require_merchant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ciba", tags=["CIBA Authorization"])


# =============================================================================
# SCHEMAS
# =============================================================================

class AuthorizationDecisionRequest(BaseModel):
    """Request body for authorization decision."""
    decision: Literal["approve", "reject"]
    
    
class AuthorizationDecisionResponse(BaseModel):
    """Response for authorization decision."""
    success: bool
    status: str
    message: str | None = None
    
    
class PendingAuthorizationResponse(BaseModel):
    """Response for pending authorization request."""
    id: str
    auth_req_id: str
    agent_type: str
    operation_type: str
    authorization_details: dict
    status: str
    expires_at: str
    created_at: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/authorize/{auth_req_id}", response_model=AuthorizationDecisionResponse)
async def authorize_request(
    auth_req_id: str,
    request: AuthorizationDecisionRequest,
    current_user: Merchant = Depends(require_merchant)
):
    """
    Mobile/dashboard endpoint to authorize or reject CIBA requests.
    
    This endpoint is called when the merchant approves or rejects
    an agent action via mobile push notification or dashboard.
    """
    ciba = CIBAService(current_user.id)
    
    result = await ciba.process_decision(
        auth_req_id=auth_req_id,
        decision="approved" if request.decision == "approve" else "rejected",
        decision_channel="api"
    )
    
    if result.get("success"):
        return AuthorizationDecisionResponse(
            success=True,
            status=result["status"],
            message=f"Request {request.decision}d successfully"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Unknown error")
        )


@router.get("/pending", response_model=List[PendingAuthorizationResponse])
async def get_pending_requests(
    current_user: Merchant = Depends(require_merchant)
):
    """
    Get all pending authorization requests for the current merchant.
    
    Returns requests that are awaiting merchant decision.
    """
    ciba = CIBAService(current_user.id)
    pending = await ciba.get_pending_requests()
    
    return [
        PendingAuthorizationResponse(
            id=req.id,
            auth_req_id=req.auth_req_id,
            agent_type=req.agent_type,
            operation_type=req.operation_type,
            authorization_details=req.authorization_details,
            status=req.status,
            expires_at=req.expires_at.isoformat(),
            created_at=req.created_at.isoformat()
        )
        for req in pending
    ]


@router.post("/approve/{auth_req_id}", response_model=AuthorizationDecisionResponse)
async def quick_approve(
    auth_req_id: str,
    current_user: Merchant = Depends(require_merchant)
):
    """Quick approve endpoint for mobile deep links."""
    ciba = CIBAService(current_user.id)
    result = await ciba.process_decision(auth_req_id, "approved", "mobile_push")
    
    if result.get("success"):
        return AuthorizationDecisionResponse(
            success=True,
            status="approved",
            message="Request approved"
        )
    raise HTTPException(status_code=400, detail=result.get("error"))


@router.post("/reject/{auth_req_id}", response_model=AuthorizationDecisionResponse)
async def quick_reject(
    auth_req_id: str,
    current_user: Merchant = Depends(require_merchant)
):
    """Quick reject endpoint for mobile deep links."""
    ciba = CIBAService(current_user.id)
    result = await ciba.process_decision(auth_req_id, "rejected", "mobile_push")
    
    if result.get("success"):
        return AuthorizationDecisionResponse(
            success=True,
            status="rejected",
            message="Request rejected"
        )
    raise HTTPException(status_code=400, detail=result.get("error"))
