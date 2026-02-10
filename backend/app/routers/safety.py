from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

from app.integrations.circuit_breaker import (
    get_klaviyo_circuit_breaker,
    get_twilio_circuit_breaker,
    get_shopify_circuit_breaker,
    get_all_circuit_statuses
)
from app.config import get_settings

router = APIRouter(prefix="/safety/circuit-breakers", tags=["Safety"])
settings = get_settings()
security = HTTPBearer()

def verify_admin(auth: HTTPAuthorizationCredentials = Security(security)):
    """Simple admin verification for safety controls."""
    # In production, this would check roles in the JWT
    if auth.credentials != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return True

@router.get("/status")
async def status():
    """Get status of all circuit breakers."""
    return get_all_circuit_statuses()

@router.post("/{service}/reset")
async def reset(service: str, authorized: bool = Depends(verify_admin)):
    """Manually reset a circuit breaker."""
    breakers = {
        "klaviyo": get_klaviyo_circuit_breaker(),
        "twilio": get_twilio_circuit_breaker(),
        "shopify": get_shopify_circuit_breaker()
    }
    
    if service not in breakers:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
        
    breakers[service].reset()
    return {"status": "success", "message": f"Circuit breaker for {service} reset"}
