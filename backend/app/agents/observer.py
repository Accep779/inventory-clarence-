# backend/app/agents/observer.py
"""
Observer Agent
==============

The "Eyes" of the system. Responsbile for identifying inventory risks,
predicting dead stock before it happens, and reasoning about product velocity.

Implements world-class patterns:
1. Dual Memory (Historical classifications)
2. Transparent Reasoning (ThoughtLogger)
3. Latent Risk Detection (LLM-driven trend analysis)
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Product, AgentThought, OrderItem
from app.services.memory import MemoryService
from app.services.thought_logger import ThoughtLogger
from app.services.llm_router import LLMRouter
from app.services.clustering import InventoryClusteringService
from app.services.memory_stream import MemoryStreamService

logger = logging.getLogger(__name__)

class ObserverAgent:
    """
    Analyzes inventory and detects risks using both deterministic logic 
    and LLM-driven reasoning.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.memory = MemoryService(merchant_id)
        self.router = LLMRouter()
        self.clustering = InventoryClusteringService(merchant_id)
        self.causal_memory = MemoryStreamService(merchant_id)
        self.agent_type = "observer"
        self._api_token = None
        self.client_id = f"agent_{self.agent_type}_99c2"

    async def _authenticate(self):
        """[HARDENING] Authenticates with Internal API using Vaulted Credentials."""
        if self._api_token: return
        import aiohttp
        from app.services.identity import IdentityService
        from app.database import async_session_maker
        async with async_session_maker() as db:
            identity_service = IdentityService(db, self.merchant_id)
            creds = await identity_service.get_agent_credentials("observer")
        if not creds:
             logger.error("Failed to fetch Observer credentials")
             return
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/auth", json=creds) as resp:
                if resp.status == 200:
                     self._api_token = (await resp.json())['access_token']
                else:
                     logger.error(f"Observer Agent Auth Failed: {await resp.text()}")

    async def _log_thought(self, **kwargs):
        """Helper to log thoughts via Internal API."""
        if not self._api_token: await self._authenticate()
        
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        
        # Map kwargs to API schema
        payload = {
            "agent_type": self.agent_type,
            "thought_type": kwargs.get("thought_type", "info"),
            "summary": kwargs.get("summary", ""),
            "detailed_reasoning": kwargs.get("detailed_reasoning", {}),
            "confidence_score": float(kwargs.get("confidence_score", 1.0)),
            "step_number": kwargs.get("step_number", 1),
            "execution_id": kwargs.get("execution_id"),
            "product_id": kwargs.get("detailed_reasoning", {}).get("product_id")
        }
        
        try:
            async with aiohttp.ClientSession() as http:
                await http.post(
                    "http://localhost:8000/internal/agents/thoughts",
                    json=payload,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"Failed to log thought via API: {e}")

    async def batch_update_status(self, analysis_results: List[Dict[str, Any]]):
        """
        Push analysis results to the Internal API.
        """
        if not self._api_token:
            await self._authenticate()
            
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        
        updates = []
        for res in analysis_results:
            # We need product_id. observe_inventory logic might need to pass it through better.
            # Assuming res has 'id' or we passed it in. 
            # Reviewing observe_inventory: it passes through keys from observe_product which returns **metrics ??
            # Need to ensure 'id' is in the result.
            if 'id' in res:
                updates.append({
                    "product_id": res['id'],
                    "is_dead_stock": res['is_dead_stock'],
                    "dead_stock_severity": res['severity'],
                    "velocity_score": float(res['velocity_score']),
                    "days_since_last_sale": int(res['days_since_last_sale'])
                })
        
        if not updates:
            return
            
        async with aiohttp.ClientSession() as http:
            async with http.post(
                "http://localhost:8000/internal/agents/inventory/status", 
                json={"updates": updates},
                headers=headers
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to push inventory updates: {await resp.text()}")

    async def observe_inventory(self, products: List[Dict[str, Any]], session) -> List[Dict[str, Any]]:
        """
        Bulk observation using Clustering + Semantic Analysis.
        Reduces tokens by summarizing thousands of products into cluster themes.
        """
        logger.info(f"Starting bulk inventory observation for {len(products)} products...")
        
        # 1. Cluster the inventory
        summaries = await self.clustering.cluster_inventory(products)
        cluster_fragment = self.clustering.generate_llm_prompt_fragment(summaries)
        
        # 2. Recall Causal History
        themes = [s['label'] for s in summaries]
        history = await self.causal_memory.get_relevant_history(themes)
        
        # 3. Analyze clusters via LLM
        prompt = f"""Analyze these inventory clusters and identify high-priority risks.
        
{cluster_fragment}

{history}

Identify which clusters represent the most 'Thematic Risk' (e.g. dying trends, seasonal shifts).
Respond with a strategic summary for the dashboard."""

        try:
            res = await self.router.complete(
                task_type='strategy_generation',
                system_prompt="You are a Retail Intelligence Observer. Reason about clusters of inventory.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            # Log the bulk thought via API
            await self._log_thought(
                thought_type="cluster_analysis",
                summary=f"Clustered {len(products)} products into {len(summaries)} themes.",
                detailed_reasoning={
                    "clusters": summaries,
                    "analysis": res['content']
                }
            )
        except Exception as e:
            logger.error(f"Bulk cluster analysis failed: {e}")

        # Fallback to individual observation for each product (existing logic)
        results = []
        for p in products:
            res = await self.observe_product(p, session)
            results.append(res)
        return results

    async def observe_product(self, product_data: Dict[str, Any], session) -> Dict[str, Any]:
        """
        Analyze a single product for risks.
        Combines deterministic velocity scores with LLM reasoning.
        """
        # 1. GATHER: Deterministic Base Metrics
        metrics = self._calculate_base_metrics(product_data)
        
        # 2. RECALL: Past observations for this product
        past_thoughts = await self.memory.recall_thoughts(
            agent_type=self.agent_type,
            product_id=product_data.get('id'),
            limit=2
        )
        
        # 3. REASON: LLM-driven latent risk detection
        reasoning = await self._reason_about_risk(product_data, metrics, past_thoughts)
        
        # 4. DECIDE: Final classification
        # Check if store is "fresh" (< 7 days) to prevent Day 0 false positives
        is_new_store = False
        if session:
            # We use session.get() if available, or a quick select
            # Note: In a high-perf scenario, cache this result
            from app.models import Merchant
            result = await session.execute(select(Merchant).where(Merchant.id == self.merchant_id))
            merchant = result.scalar_one_or_none()
            if merchant:
                delta = datetime.utcnow() - merchant.created_at
                if delta.days < 7:
                    is_new_store = True

        # [FIX] Check product age to prevent new products from being flagged as dead stock
        product_created_at = product_data.get('created_at')
        is_new_product = False
        if product_created_at:
            if isinstance(product_created_at, str):
                try:
                    product_created_at = datetime.fromisoformat(product_created_at.replace('Z', '+00:00'))
                except ValueError:
                    product_created_at = None
            if product_created_at:
                product_age_days = (datetime.utcnow() - product_created_at.replace(tzinfo=None)).days
                if product_age_days < 30:
                    is_new_product = True

        classification = self._finalize_classification(metrics, reasoning, is_new_store, is_new_product)
        
        # 5. LOG: Transparent reasoning via API
        await self._log_thought(
            thought_type="observation",
            summary=f"Analyzed '{product_data.get('title')}': {classification['severity']} risk detected.",
            detailed_reasoning={
                "metrics": metrics,
                "reasoning": reasoning,
                "classification": classification,
                "is_new_store": is_new_store,
                "past_observations_count": len(past_thoughts),
                "product_id": product_data.get('id')
            }
        )

        
        return {
            "id": product_data.get('id'), # Ensure ID is passed back for API update
            **metrics,
            **classification,
            "reasoning": reasoning.get("summary", ""),
            "is_dead_stock": classification["severity"] != "none"
        }

    def _calculate_base_metrics(self, data: Dict) -> Dict:
        """Calculate deterministic velocity and turnover metrics."""
        variants = data.get("variants", [])
        if variants:
            price = float(variants[0].get("price", 0))
            inventory = sum(v.get("inventory_quantity", 0) for v in variants)
        else:
            # Fallback to top-level fields if variants are missing
            price = float(data.get("price", 0))
            inventory = int(data.get("total_inventory", 0))
        
        days_since_sale = data.get("days_since_last_sale", 180)
        
        # [FINTECH FIX]: Subtract refunds to get TRUE velocity
        gross_units_30d = data.get("units_sold_30d", 0)
        refunds_30d = data.get("units_refunded_30d", 0)
        net_units_30d = max(0, gross_units_30d - refunds_30d)
        
        # Core velocity math
        avg_inventory = max(inventory, 1)
        turnover_rate = (net_units_30d / avg_inventory) * 12
        
        # Performance normalized (0-100)
        turnover_norm = min(turnover_rate / 12, 1.0) * 100
        recency_norm = max(0, (180 - days_since_sale) / 180) * 100
        
        velocity_score = (turnover_norm * 0.6) + (recency_norm * 0.4)
        
        return {
            "price": price,
            "inventory": inventory,
            "stuck_value": price * inventory,
            "velocity_score": round(velocity_score, 1),
            "turnover_rate": round(turnover_rate, 2),
            "days_since_last_sale": days_since_sale
        }

    async def _reason_about_risk(self, product: Dict, metrics: Dict, past_thoughts: List) -> Dict:
        """Use LLM to detect latent risks or validate thresholds."""
        
        prompt = f"""Reason about the inventory risk for this product. 
Detect latent risks (like rapid deceleration) that simple thresholds might miss.

PRODUCT: {product.get('title')}
CATEGORY: {product.get('product_type')}
METRICS:
- Velocity Score: {metrics['velocity_score']}/100
- Days Since Sale: {metrics['days_since_last_sale']}
- Inventory: {metrics['inventory']} units
- Stock Value: ${metrics['stuck_value']}

PAST OBSERVATIONS:
{json.dumps([t['summary'] for t in past_thoughts]) if past_thoughts else "None"}

Consider:
1. Is this seasonal? (e.g. Parkas in Spring)
2. Is the velocity dropping? 
3. Should we intervene NOW even if it's not 'critical' yet?

Respond with JSON:
{{
    "latent_risk": true/false,
    "severity_bonus": 0-2 (0=none, 1=boost, 2=critical boost),
    "summary": "Reasoning string",
    "recommendation": "monitor/act/ignore"
}}"""

        try:
            response = await self.router.complete(
                task_type="strategy_generation", # Reuse strategy router for reasoning
                system_prompt="You are a Retail Intelligence Observer. Spot risks before they become disasters.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            content = response['content'].strip()
            if '```' in content:
                content = content.split('```')[1].replace('json', '')
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"Observer reasoning failed: {e}")
            return {"latent_risk": False, "severity_bonus": 0, "summary": "Threshold-only scan.", "recommendation": "monitor"}

    def _finalize_classification(self, metrics: Dict, reasoning: Dict, is_new_store: bool = False, is_new_product: bool = False) -> Dict:
        """
        Determine final risk level combining math + brain.
        Includes 'Freshness Guard' for new stores AND new products.
        """
        score = metrics['velocity_score']
        days = metrics['days_since_last_sale']
        bonus = reasoning.get('severity_bonus', 0)
        
        # Base classification logic (Deterministic)
        if score < 20 and days >= 90:
            base_severity = "critical"
        elif score < 35:
            base_severity = "high"
        elif score < 50:
            base_severity = "moderate"
        elif score < 65:
            base_severity = "low"
        else:
            base_severity = "none"
            
        # Apply AI Bonus (The "Reflex" upgrade)
        severities = ["none", "low", "moderate", "high", "critical"]
        current_idx = severities.index(base_severity)
        final_idx = min(len(severities) - 1, current_idx + bonus)
        
        final_severity = severities[final_idx]
        
        # [Day 0 Reliability] Freshness Guard
        # If new store, cap severity at 'low' to avoid scaring merchant with 'critical' dead stock
        # that is simply legacy data from before they installed.
        if is_new_store and final_severity in ("critical", "high", "moderate"):
            final_severity = "low"
        
        # [FIX] New Product Guard: Products < 30 days old should NOT be flagged as dead stock
        # They simply haven't had enough time to sell yet
        if is_new_product and final_severity in ("critical", "high"):
            final_severity = "none"  # Too new to classify as dead stock
        
        return {
            "severity": final_severity,
            "is_latent": reasoning.get("latent_risk", False)
        }
