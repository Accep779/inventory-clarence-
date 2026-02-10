"""
Inventory Clearance Agent - FastAPI Application Entry Point.

This is the main entry point for the autonomous inventory clearance agent.
The agent operates with minimal human intervention, proposing clearance
strategies via an Inbox-First Control Surface.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, webhooks, inbox, products, merchants, strategy, thoughts, campaigns, dna, scan, safety


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")
    
    yield
    
    # Shutdown: Cleanup
    await engine.dispose()
    print("Database connection closed")


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous AI Agent for Shopify Inventory Clearance & Customer Reactivation",
    version="1.0.0",
    lifespan=lifespan,
)

# [SECURITY] Rate Limiting - Protect against abuse
# from slowapi import _rate_limit_exceeded_handler
# from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware (for Next.js frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        settings.FRONTEND_URL,  # Use configured frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# [SECURITY FIX] Security Headers Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import os

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Legacy XSS filter
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Force HTTPS in production
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Include Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["Inbox"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(merchants.router, prefix="/api/merchants", tags=["Merchants"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["Strategy"])
app.include_router(thoughts.router, prefix="/api/thoughts", tags=["Thoughts"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(dna.router, prefix="/api/dna", tags=["Store DNA"])
app.include_router(scan.router, prefix="/api/scan", tags=["Scan"])
app.include_router(safety.router, prefix="/api/safety", tags=["Safety"])
# [NEW] Universal Gateway
from app.routers import gateway
app.include_router(gateway.router)

# [NEW] Command Center APIs
from app.routers import skills, digest
app.include_router(skills.router)
app.include_router(digest.router)


# Analytics Webhooks (Feedback Loop)
from app.routers import webhooks_analytics
app.include_router(webhooks_analytics.router, prefix="/api/webhooks/analytics", tags=["Analytics Webhooks"])

# Seasonal Transition Agent
from app.routers import seasonal
app.include_router(seasonal.router, tags=["Seasonal"])
# System Analytics & CRM
from app.routers import analytics, crm
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(crm.router, prefix="/api/crm", tags=["CRM"])

# Internal Agent API (Protected)
from app.routers import internal_api
app.include_router(internal_api.router)

from fastapi import Depends, HTTPException
from sqlalchemy import text
from app.database import get_db

@app.get("/health")
async def health_check(db=Depends(get_db)):
    """Deep Health Check: Verifies Database Connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        print(f"Health check failed: {e}")
        # Return 503 so load balancers know to stop sending traffic
        raise HTTPException(status_code=503, detail="Database disconnected")


@app.get("/")
async def root():
    """Root endpoint with system info."""
    return {
        "name": settings.APP_NAME,
        "status": "operational",
        "agents": {
            "observer": "active",
            "strategy": "active",
            "matchmaker": "active",
            "execution": "standby",
            "broker": "standby",
        },
    }
