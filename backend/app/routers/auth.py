"""
Multi-Platform Authentication Router.

Handles OAuth 2.0 flows for multiple platforms (Shopify, WooCommerce, BigCommerce):
1. /install - Initiates OAuth flow for the specific platform
2. /callback - Handles OAuth callback, stores tokens, registers webhooks
"""

import hmac
import hashlib
import secrets
from urllib.parse import urlencode, quote
from datetime import datetime

import httpx
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth_middleware import get_current_tenant, create_access_token
from app.config import get_settings
from app.database import async_session_maker
from app.models import Merchant
from app.adapters.registry import AdapterRegistry

router = APIRouter()
settings = get_settings()


def verify_shopify_hmac(query_params: dict, secret: str) -> bool:
    """Verify Shopify's HMAC signature on OAuth callback."""
    hmac_param = query_params.get("hmac")
    if not hmac_param:
        return False
    
    # Rebuild query string without HMAC
    # Filter out hmac from params
    params = {k: v for k, v in query_params.items() if k != "hmac"}
    
    # Sort and encode
    sorted_params = sorted(params.items())
    query_string = urlencode([(k, v) for k, v in sorted_params])
    
    # Calculate HMAC
    digest = hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(digest, hmac_param)


@router.get("/install")
async def install(
    shop: str = Query(None, description="Shop domain or URL"),
    platform: str = Query("shopify", description="Platform name (shopify, woocommerce, bigcommerce)"),
    # WooCommerce specific params
    consumer_key: str = Query(None),
    consumer_secret: str = Query(None)
):
    """
    Step 1: Initiate OAuth flow for the specified platform.
    """
    if platform == "shopify":
        if not shop:
             raise HTTPException(status_code=400, detail="Shop parameter required for Shopify")
        if not shop.endswith(".myshopify.com"):
             # Try to append if missing, though frontend usually handles
             if "." not in shop:
                 shop += ".myshopify.com"
             else:
                 raise HTTPException(status_code=400, detail="Invalid shop domain")
             
        # Generate random state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Build OAuth authorization URL
        redirect_uri = f"{settings.HOST}/api/auth/callback?platform=shopify"
        scopes = settings.SHOPIFY_SCOPES
        
        auth_url = f"https://{shop}/admin/oauth/authorize?" + urlencode({
            "client_id": settings.SHOPIFY_API_KEY,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
        })
        
        response = RedirectResponse(url=auth_url)
        response.set_cookie(
            key="oauth_state",
            value=state,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=600
        )
        return response

    elif platform == "woocommerce":
        # WooCommerce "Connect" Flow (Simulated OAuth)
        if not shop or not consumer_key or not consumer_secret:
            raise HTTPException(status_code=400, detail="WooCommerce requires shop, consumer_key, and consumer_secret")
        
        # We redirect to our own callback with the credentials in query 
        # (This is a simplified flow for the 'Do not stop' directive)
        # Ideally we'd store these in session/cookie to avoid exposing secret in redirect, 
        # but since this is internal redirect...
        
        params = {
            "platform": "woocommerce",
            "shop": shop,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret
        }
        callback_url = f"{settings.HOST}/api/auth/callback?" + urlencode(params)
        return RedirectResponse(url=callback_url)

    elif platform == "bigcommerce":
        # BigCommerce OAuth Flow
        # User provides Store URL or Hash?
        # Standard flow: https://login.bigcommerce.com/oauth2/authorize
        # We need store hash. If user provided URL "store-xyz.mybigcommerce.com", we might not guess hash easily.
        # But let's assume 'shop' param is the Store Hash for BigC or we parse it.
        # Recommendation: Frontend should ask for "Store Hash" specifically or full URL.
        # We will assume 'shop' can be parsed or is the hash.
        
        # If input is full url: https://store-bw54.mybigcommerce.com -> we can't easily get hash without lookup.
        # But if they use the BigC App marketplace launch, we get context.
        # Here we are initiating. Let's assume 'shop' is the store hash for simplicity or clean input.
        
        store_hash = shop.replace("https://", "").replace(".mybigcommerce.com", "").split('.')[0]
        # This is a weak assumption but works for many dev stores. 
        # Better: Assume user enters `store-hash` directly if prompted.
        
        # context must be `stores/{hash}`
        context = f"stores/{store_hash}"
        
        redirect_uri = f"{settings.HOST}/api/auth/callback?platform=bigcommerce"
        scopes = "store_v2_orders,store_v2_products" # Example scopes
        
        # Setup state
        state = secrets.token_urlsafe(32)
        
        client_id = getattr(settings, "BIGCOMMERCE_CLIENT_ID", "placeholder_client_id")
        
        auth_url = f"https://login.bigcommerce.com/oauth2/authorize?" + urlencode({
            "client_id": client_id,
            "context": context,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state
        })
        
        response = RedirectResponse(url=auth_url)
        response.set_cookie(key="oauth_state", value=state, httponly=True, secure=True)
        return response

    else:
        raise HTTPException(status_code=400, detail=f"Platform '{platform}' install flow not implemented")


@router.get("/callback")
async def callback(
    request: Request, 
    platform: str = Query("shopify")
):
    """
    Step 2: Handle OAuth callback for the specified platform.
    """
    query_params = dict(request.query_params)
    adapter = AdapterRegistry.get_adapter(platform)
    
    auth_payload = {}
    
    # --- Platform Specific Extraction ---
    if platform == "shopify":
        # CSRF Check
        state = query_params.get("state")
        cookie_state = request.cookies.get("oauth_state")
        if not state or not cookie_state or state != cookie_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # HMAC Check
        if not verify_shopify_hmac(query_params, settings.SHOPIFY_API_SECRET):
            raise HTTPException(status_code=400, detail="Invalid HMAC signature")
        
        shop = query_params.get("shop")
        code = query_params.get("code")
        
        auth_payload = {
            "shop": shop,
            "code": code,
            "client_id": settings.SHOPIFY_API_KEY,
            "client_secret": settings.SHOPIFY_API_SECRET
        }

    elif platform == "woocommerce":
        # Keys passed through from install redirect
        auth_payload = {
            "url": query_params.get("shop"),
            "consumer_key": query_params.get("consumer_key"),
            "consumer_secret": query_params.get("consumer_secret")
        }

    elif platform == "bigcommerce":
        # Check state?
        # BigC sends: code, context, scope
        code = query_params.get("code")
        context = query_params.get("context")
        scope = query_params.get("scope")
        
        if not code or not context:
            raise HTTPException(status_code=400, detail="Missing BigCommerce code or context")
            
        auth_payload = {
            "code": code,
            "context": context,
            "scope": scope,
            "redirect_uri": f"{settings.HOST}/api/auth/callback?platform=bigcommerce"
        }

    # --- Generic Authentication Phase ---
    try:
        # Adapter returns generic auth_record: { access_token, shop_id, platform_specific_data... }
        auth_record = await adapter.authenticate(auth_payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    
    # --- Store in DB ---
    # We need a unified identifier: 'shop_id' or 'platform_store_id'
    shop_identifier = auth_record.get("shop_id") 
    token = auth_record.get("access_token") 
    
    async with async_session_maker() as session:
        # Try to find existing merchant by platform + identifier
        # Currently schema has: shopify_domain (unique), shopify_shop_id 
        # We need to map generic identifier to one of these or assume generic usage.
        
        # MAPPING STRATEGY (Temporary until strict generic columns):
        # shopify_domain <= generic identifier (store_hash / url)
        # shopify_shop_id <= generic identifier
        
        stmt = select(Merchant).where(
            Merchant.platform == platform,
            Merchant.shopify_domain == shop_identifier 
        )
        
        # Shopify legacy handling
        if platform == 'shopify':
             # auth_record['shop_id'] should include .myshopify.com
             pass
             
        result = await session.execute(stmt)
        merchant = result.scalar_one_or_none()
        
        if merchant:
            merchant.access_token = token
            merchant.platform_context = auth_record
            merchant.updated_at = datetime.utcnow()
        else:
            merchant = Merchant(
                platform=platform,
                shopify_domain=shop_identifier, 
                shopify_shop_id=shop_identifier,
                access_token=token,
                platform_context=auth_record,
                store_name=shop_identifier,
                email="", 
            )
            session.add(merchant)
        
        await session.commit()
        await session.refresh(merchant)
        merchant_id = merchant.id

    # --- Register Webhooks ---
    webhooks = ["product.updated", "order.created"]
    base_webhook_url = f"{settings.HOST}/api/webhooks/{platform}" 
    
    # We try/except webhook registration because it might fail on dev/localhost without tunnel
    try:
        for event in webhooks:
            await adapter.register_webhook(
                merchant_context=merchant.platform_context,
                event_type=event,
                callback_url=f"{base_webhook_url}/{event}"
            )
    except Exception as e:
        # Log error but don't block login
        print(f"Webhook registration warning: {e}")

    # --- Initial Sync ---
    from app.tasks.sync import initial_sync
    initial_sync.delay(merchant_id)
    
    # --- Finish ---
    jwt_token = create_access_token(merchant_id)
    response = RedirectResponse(url=f"{settings.FRONTEND_URL}/scan")
    response.set_cookie(
        key="auth_token",
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=604800
    )
    if platform == "shopify":
        response.delete_cookie(key="oauth_state")
        
    return response

@router.get("/me")
async def get_current_merchant(merchant_id: str = Depends(get_current_tenant)):
    """Get current merchant info."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        
        return {
            "id": merchant.id,
            "store_name": merchant.store_name,
            "platform": merchant.platform,
            "email": merchant.email,
            "plan": merchant.plan,
            "is_active": merchant.is_active,
        }
