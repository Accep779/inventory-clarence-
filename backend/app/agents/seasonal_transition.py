# backend/app/agents/seasonal_transition.py
"""
Seasonal Transition Agent
=========================

A world-class AI agent that identifies seasonal inventory risks and 
proactively generates clearance strategies before stock becomes dead weight.

Implements all 7 world-class patterns:
1. Dual Memory (MemoryService)
2. Plan-Criticize-Act (self-critique before strategy selection)
3. Self-Verification (verify after proposal creation)
4. Transparent Reasoning (ThoughtLogger)
5. Task Decomposition (3 clearance windows)
6. Reflection on Failure (FailureReflector integration)
7. Continuous Learning (accumulated lessons in prompts)
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Product, Merchant, InboxItem, Order, OrderItem, StoreDNA
from app.services.seasonal_analyzer import SeasonalAnalyzer, SeasonalRisk, Season
from app.services.memory import MemoryService
# from app.services.thought_logger import ThoughtLogger # Removed direct dependency
from app.services.llm_router import LLMRouter
from app.services.governor import GovernorService, AutonomyDecision
from app.agents.strategy import STRATEGIES

logger = logging.getLogger(__name__)


class SeasonalTransitionAgent:
    """
    Identifies seasonal products at risk and generates clearance strategies.
    
    Uses Plan-Criticize-Act pattern for world-class decision making.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.analyzer = SeasonalAnalyzer()
        self.memory = MemoryService(merchant_id)
        self.router = LLMRouter()
        self.agent_type = "seasonal"
        self._api_token = None
        self.client_id = f"agent_{self.agent_type}_season_v1"

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
            "product_id": kwargs.get("detailed_reasoning", {}).get("product_id") or kwargs.get("product_id")
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

    async def _authenticate(self):
        """[HARDENING] Authenticates with Internal API using Vaulted Credentials."""
        if self._api_token: return
        import aiohttp
        from app.services.identity import IdentityService
        from app.database import async_session_maker
        async with async_session_maker() as db:
            identity_service = IdentityService(db, self.merchant_id)
            creds = await identity_service.get_agent_credentials("seasonal")
        if not creds:
             logger.error("Failed to fetch Seasonal credentials")
             return
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/auth", json=creds) as resp:
                if resp.status == 200:
                     self._api_token = (await resp.json())['access_token']
                else:
                     logger.error(f"Seasonal Auth Failed: {await resp.text()}")
    
    async def scan_seasonal_risks(
        self,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan all products for seasonal risks.
        
        Returns list of products with risk assessments.
        """
        execution_id = str(uuid.uuid4())
        
        await self._log_thought(
            thought_type="observation",
            summary="Starting seasonal risk scan",
            execution_id=execution_id,
            step_number=1
        )
        
        async with async_session_maker() as session:
            # Fetch products with orders for velocity analysis
            result = await session.execute(
                select(Product)
                .where(Product.merchant_id == self.merchant_id)
                .where(Product.total_inventory > 0)
                .options(selectinload(Product.variants))
            )
            products = result.scalars().all()
            
            # 2. BATCH FETCH: Sample historical orders for all products to avoid N+1
            # We fetch up to 20 orders per product for risk analysis
            from sqlalchemy import over
            order_stmt = (
                select(OrderItem.product_id, Order.order_date)
                .join(Order, Order.id == OrderItem.order_id)
                .where(OrderItem.product_id.in_([p.id for p in products]))
                .order_by(Order.order_date.desc())
            )
            order_res = await session.execute(order_stmt)
            
            # Group orders by product
            product_orders = {}
            for row in order_res.all():
                p_id, o_date = row
                if p_id not in product_orders:
                    product_orders[p_id] = []
                if len(product_orders[p_id]) < 20:
                    product_orders[p_id].append({'created_at': o_date})

            risks = []
            for i, product in enumerate(products):
                # Convert to dict for analyzer
                product_dict = {
                    'id': product.id,
                    'title': product.title,
                    'description': product.body_html or '',
                    'tags': product.tags.split(',') if product.tags else [],
                    'product_type': product.product_type or '',
                    'vendor': product.vendor or ''
                }
                
                # Get historical orders for this product from our batch fetch
                orders = product_orders.get(product.id, [])
                
                # Assess risk
                risk = self.analyzer.assess_risk(product_dict, orders)
                
                if risk.risk_level in ['critical', 'high', 'moderate']:
                    risks.append({
                        'product': product,
                        'risk': risk
                    })
                
                # Progress callback for SSE
                if progress_callback and i % 10 == 0:
                    await progress_callback({
                        'scanned': i + 1,
                        'total': len(products),
                        'risks_found': len(risks)
                    })
            
            await self._log_thought(
                thought_type="observation",
                summary=f"Scan complete. Found {len(risks)} at-risk seasonal products.",
                detailed_reasoning={
                    'total_products': len(products),
                    'at_risk': len(risks),
                    'risk_breakdown': {
                        'critical': len([r for r in risks if r['risk'].risk_level == 'critical']),
                        'high': len([r for r in risks if r['risk'].risk_level == 'high']),
                        'moderate': len([r for r in risks if r['risk'].risk_level == 'moderate'])
                    }
                },
                execution_id=execution_id,
                step_number=2
            )
            
            return risks
    
    async def plan_seasonal_clearance(
        self,
        product_id: str,
        risk: SeasonalRisk
    ) -> Dict[str, Any]:
        """
        Plan a clearance strategy for a seasonal product.
        
        Implements the full Plan-Criticize-Act pattern.
        """
        execution_id = str(uuid.uuid4())
        
        async with async_session_maker() as session:
            # 1. GATHER: Fetch all context
            product = await session.get(Product, product_id, options=[selectinload(Product.variants)])
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            merchant_result = await session.execute(
                select(Merchant).where(Merchant.id == self.merchant_id)
            )
            merchant = merchant_result.scalar_one_or_none()
            
            # Log initial observation
            await self._log_thought(
                thought_type="observation",
                summary=f"Planning seasonal clearance for '{product.title}'",
                detailed_reasoning={
                    'product_id': product_id,
                    'season': risk.detected_season.value,
                    'days_remaining': risk.days_until_season_end,
                    'risk_level': risk.risk_level
                },
                execution_id=execution_id,
                step_number=1
            )
            
            # 2. PLAN: Select initial strategy
            clearance_window = SeasonalAnalyzer.get_clearance_window(risk.days_until_season_end)
            initial_strategy = await self._select_strategy(
                product, risk, clearance_window, session
            )
            
            # 3. CRITICIZE: Self-critique the strategy
            criticism = await self._criticize_strategy(
                product, risk, initial_strategy, session
            )
            
            # 4. REVISE: Adjust if criticism rejected
            final_strategy = initial_strategy
            if not criticism['approved']:
                if criticism['alternative'] in STRATEGIES:
                    final_strategy = criticism['alternative']
                    await self._log_thought(
                        thought_type="decision",
                        summary=f"Revised strategy from '{initial_strategy}' to '{final_strategy}' based on self-critique",
                        detailed_reasoning=criticism,
                        execution_id=execution_id,
                        step_number=3
                    )
            
            # 5. CALCULATE: Pricing with floor constraints
            pricing = await self._calculate_pricing(product, final_strategy, risk, session)
            
            # 6. GENERATE: LLM-powered campaign copy
            copy = await self._generate_campaign_copy(product, risk, final_strategy, pricing)
            
            # 7. PROJECT: Revenue vs holding cost
            projections = self._calculate_projections(product, pricing, risk)
            
            # 8. CREATE: InboxItem proposal
            proposal = await self._create_proposal(
                product=product,
                risk=risk,
                strategy=final_strategy,
                pricing=pricing,
                copy=copy,
                projections=projections,
                criticism=criticism,
                session=session,
                execution_id=execution_id
            )
            
            # 9. VERIFY: Post-creation verification
            verification = await self._verify_proposal(proposal, product, risk)
            
            await session.commit()
            
            return {
                'status': 'success',
                'proposal_id': proposal.id,
                'strategy': final_strategy,
                'risk': {
                    'level': risk.risk_level,
                    'season': risk.detected_season.value,
                    'days_remaining': risk.days_until_season_end
                },
                'pricing': pricing,
                'projections': projections,
                'criticism': criticism,
                'verification': verification
            }
    
    async def _select_strategy(
        self,
        product: Product,
        risk: SeasonalRisk,
        window: str,
        session
    ) -> str:
        """
        LLM-driven strategy selection with memory integration.
        """
        # Recall past outcomes and lessons
        past_outcomes = await self.memory.recall_campaign_outcomes(product_id=product.id, limit=3)
        preferences = await self.memory.get_merchant_preferences()
        
        # Get accumulated lessons
        from app.services.failure_reflector import FailureReflector
        reflector = FailureReflector(self.merchant_id)
        lessons = await reflector.get_accumulated_lessons(limit=5)
        
        # Build context-rich prompt
        prompt = f"""Select the optimal clearance strategy for this SEASONAL product.

PRODUCT DATA:
- Title: {product.title}
- Season: {risk.detected_season.value}
- Days Until Season End: {risk.days_until_season_end}
- Risk Level: {risk.risk_level}
- Clearance Window: {window}
- Inventory: {product.total_inventory}
- Price: ${float(product.variants[0].price) if product.variants else 0:.2f}

SEASONAL URGENCY:
- Pre-season end (30+ days): Can use gradual discounts
- Season end (14-30 days): Need aggressive action
- Post-season (0-14 days): Maximum urgency, liquidation mode

PAST CAMPAIGNS FOR THIS PRODUCT:
{json.dumps([{'strategy': o['strategy'], 'success': o['success']} for o in past_outcomes], indent=2) if past_outcomes else 'None'}

LESSONS FROM PAST FAILURES:
{chr(10).join([f"- {l}" for l in lessons]) if lessons else 'No lessons yet'}

MERCHANT PREFERENCES:
- Brand Tone: {preferences.get('brand_tone', 'professional')}
- Max Discount: {preferences.get('max_auto_discount', 0.25):.0%}

AVAILABLE STRATEGIES: {list(STRATEGIES.keys())}

Select the strategy that balances urgency with brand preservation.
Respond with ONLY the strategy key."""

        try:
            response = await self.router.complete(
                task_type='strategy_generation',
                system_prompt="You are a seasonal clearance expert. Select the optimal strategy based on timing urgency.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            strategy = response['content'].strip().lower().replace('"', '').replace("'", "")
            
            if strategy in STRATEGIES:
                return strategy
            else:
                return self._fallback_strategy(risk, window)
                
        except Exception as e:
            logger.warning(f"LLM strategy selection failed: {e}. Using fallback.")
            return self._fallback_strategy(risk, window)
    
    def _fallback_strategy(self, risk: SeasonalRisk, window: str) -> str:
        """Deterministic fallback when LLM fails."""
        if window == 'post_season' or risk.risk_level == 'critical':
            return 'aggressive_liquidation'
        elif window == 'season_end' or risk.risk_level == 'high':
            return 'flash_sale'
        else:
            return 'progressive_discount'
    
    async def _criticize_strategy(
        self,
        product: Product,
        risk: SeasonalRisk,
        strategy: str,
        session
    ) -> Dict[str, Any]:
        """
        WORLD-CLASS: Self-critique before executing.
        """
        preferences = await self.memory.get_merchant_preferences()
        
        prompt = f"""Critically evaluate this seasonal clearance strategy.

PROPOSED:
- Strategy: {strategy}
- Product: {product.title}
- Season: {risk.detected_season.value}
- Days Left: {risk.days_until_season_end}
- Risk: {risk.risk_level}

CONCERNS TO CHECK:
1. Is this too aggressive for the brand tone ({preferences.get('brand_tone', 'professional')})?
2. Is this not aggressive ENOUGH given {risk.days_until_season_end} days remaining?
3. Does this strategy make sense for {risk.detected_season.value} products?
4. Will this protect margins adequately?

Respond with JSON:
{{
    "approval": true/false,
    "concerns": ["concern 1", "concern 2"],
    "suggestion": "alternative_strategy or proceed",
    "confidence": 0.0-1.0
}}"""

        try:
            response = await self.router.complete(
                task_type='strategy_generation',
                system_prompt="Be a skeptical critic. Find flaws. JSON only.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            content = response['content'].strip()
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            criticism = json.loads(content)
            
            await self._log_thought(
                thought_type="criticism",
                summary=f"Strategy critique: {'Approved' if criticism.get('approval') else 'Concerns'}",
                detailed_reasoning=criticism
            )
            
            return {
                'approved': criticism.get('approval', True),
                'concerns': criticism.get('concerns', []),
                'alternative': criticism.get('suggestion', 'proceed'),
                'confidence': criticism.get('confidence', 0.8)
            }
            
        except Exception as e:
            logger.warning(f"Criticism failed: {e}")
            return {'approved': True, 'concerns': [], 'alternative': 'proceed', 'confidence': 0.5}
    
    async def _calculate_pricing(
        self,
        product: Product,
        strategy: str,
        risk: SeasonalRisk,
        session
    ) -> Dict[str, Any]:
        """Calculate pricing with floor constraints."""
        if not product.variants:
            return {'error': 'No variants'}
        
        original_price = float(product.variants[0].price)
        cost = float(product.cost_per_unit) if product.cost_per_unit else (original_price * 0.4)
        
        # Strategy-based discount
        strategy_config = STRATEGIES.get(strategy, {})
        base_discount = strategy_config.get('discount_range', (0.1, 0.2))
        
        # Urgency adjustment
        if risk.days_until_season_end <= 7:
            urgency_boost = 0.15
        elif risk.days_until_season_end <= 14:
            urgency_boost = 0.10
        else:
            urgency_boost = 0.0
        
        discount = min(0.50, base_discount[1] + urgency_boost)
        sale_price = original_price * (1 - discount)
        
        # Floor pricing check
        from app.models import FloorPricing
        floor_result = await session.execute(
            select(FloorPricing)
            .where(FloorPricing.merchant_id == self.merchant_id)
            .where(FloorPricing.product_id == product.id)
        )
        floor = floor_result.scalar_one_or_none()
        
        if floor and sale_price < float(floor.floor_price):
            sale_price = float(floor.floor_price)
            discount = 1 - (sale_price / original_price)
        
        margin = (sale_price - cost) / sale_price if sale_price > 0 else 0
        
        return {
            'original_price': original_price,
            'sale_price': round(sale_price, 2),
            'discount_percent': round(discount * 100, 1),
            'margin_percent': round(margin * 100, 1),
            'cost': cost,
            'floor_applied': floor is not None and sale_price == float(floor.floor_price) if floor else False
        }
    
    async def _generate_campaign_copy(
        self,
        product: Product,
        risk: SeasonalRisk,
        strategy: str,
        pricing: Dict
    ) -> Dict[str, Any]:
        """Generate seasonal-aware campaign copy."""
        
        # Get store DNA for brand voice
        async with async_session_maker() as session:
            dna_result = await session.execute(
                select(StoreDNA).where(StoreDNA.merchant_id == self.merchant_id)
            )
            store_dna = dna_result.scalar_one_or_none()
        
        brand_tone = store_dna.brand_tone if store_dna else 'friendly'
        
        prompt = f"""Write campaign copy for an end-of-season sale.

PRODUCT: {product.title}
SEASON: {risk.detected_season.value}
DISCOUNT: {pricing['discount_percent']}% off
SALE PRICE: ${pricing['sale_price']}
URGENCY: {risk.days_until_season_end} days left
BRAND TONE: {brand_tone}

Generate:
1. Email subject line (max 50 chars)
2. Email headline
3. Email body (2-3 sentences)
4. SMS message (max 160 chars)

Respond with JSON:
{{
    "subject": "...",
    "headline": "...",
    "body": "...",
    "sms": "..."
}}"""

        try:
            response = await self.router.complete(
                task_type='copy_generation',
                system_prompt=f"You write {brand_tone} marketing copy. Be concise and compelling.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            content = response['content'].strip()
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            return json.loads(content)
            
        except Exception as e:
            logger.warning(f"Copy generation failed: {e}")
            return {
                'subject': f"End of {risk.detected_season.value.title()} Sale",
                'headline': f"{pricing['discount_percent']:.0f}% Off {product.title}",
                'body': f"Don't miss out on this end-of-season deal!",
                'sms': f"{pricing['discount_percent']:.0f}% off {product.title}! Limited time."
            }
    
    def _calculate_projections(
        self,
        product: Product,
        pricing: Dict,
        risk: SeasonalRisk
    ) -> Dict[str, Any]:
        """Calculate revenue projections vs holding costs."""
        inventory = product.total_inventory or 0
        sale_price = pricing.get('sale_price', 0)
        cost = pricing.get('cost', 0)
        
        # Projected sales (based on risk level)
        conversion_rates = {
            'critical': 0.6,
            'high': 0.4,
            'moderate': 0.25,
            'low': 0.15
        }
        conversion = conversion_rates.get(risk.risk_level, 0.2)
        
        projected_units = int(inventory * conversion)
        projected_revenue = projected_units * sale_price
        projected_profit = projected_units * (sale_price - cost)
        
        # Holding cost if we don't clear
        monthly_holding = inventory * cost * 0.02  # 2% per month
        holding_cost_6mo = monthly_holding * 6
        
        return {
            'inventory_at_risk': inventory,
            'projected_units_sold': projected_units,
            'projected_revenue': round(projected_revenue, 2),
            'projected_profit': round(projected_profit, 2),
            'holding_cost_6mo': round(holding_cost_6mo, 2),
            'recommendation': 'clear' if projected_profit > holding_cost_6mo else 'hold'
        }
    
    async def _create_proposal(
        self,
        product: Product,
        risk: SeasonalRisk,
        strategy: str,
        pricing: Dict,
        copy: Dict,
        projections: Dict,
        criticism: Dict,
        session,
        execution_id: str
    ) -> InboxItem:
        """Create InboxItem proposal for merchant approval."""
        
        # [SECURE REFACTOR] Use Internal API
        await self._authenticate()
        if self._api_token:
            import aiohttp
            headers = {"Authorization": f"Bearer {self._api_token}"}
            
            payload = {
                "title": f"Seasonal Clearance: {product.title}",
                "description": f"Risk Level: {risk.risk_level}",
                "pricing": pricing,
                "strategy": strategy,
                "discount_percent": pricing['discount_percent'],
                "projected_revenue": projections['projected_revenue'],
                "copy_data": {
                    'email_subject': copy.get('subject', ''),
                    'email_headline': copy.get('headline', ''),
                    'email_body': copy.get('body', ''),
                    'sms_message': copy.get('sms', '')
                },
                "reasoning": {
                    'seasonal_risk': {
                        'season': risk.detected_season.value,
                        'days_remaining': risk.days_until_season_end,
                        'risk_level': risk.risk_level,
                        'velocity_decline': risk.predicted_velocity_decline
                    },
                    'strategy_selection': {
                        'selected': strategy,
                        'criticism': criticism,
                        'revised': not criticism['approved']
                    },
                    'projections': projections,
                    'pricing': pricing
                }
            }
            
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    "http://localhost:8000/internal/agents/proposals",
                    json=payload,
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        from types import SimpleNamespace
                        return SimpleNamespace(
                            id=res_data['id'],
                            discount_percent=pricing['discount_percent'],
                            projected_revenue=projections['projected_revenue'],
                            copy_data=payload['copy_data']
                        )
                    else:
                        logger.error(f"Failed to create proposal: {await resp.text()}")
                        raise Exception("API Proposal Creation Failed")

        # Fallback if logic fails (should not happen in prod if enforced)
        # But for type hints/flow, we might arguably error out.
        raise Exception("Agent Authentication Required for write operations")
    
    async def _verify_proposal(
        self,
        proposal: InboxItem,
        product: Product,
        risk: SeasonalRisk
    ) -> Dict[str, Any]:
        """
        WORLD-CLASS: Verify the proposal before returning.
        """
        issues = []
        verified = True
        
        # Check: Does proposal have all required fields?
        if not proposal.copy_data or not proposal.copy_data.get('email_subject'):
            issues.append("Missing campaign copy")
            verified = False
        
        # Check: Is discount reasonable?
        if proposal.discount_percent > 50:
            issues.append(f"Discount {proposal.discount_percent}% may be too aggressive")
        
        # Check: Is projected revenue positive?
        if proposal.projected_revenue <= 0:
            issues.append("Projected revenue is zero or negative")
            verified = False
        
        # Check: Does timing make sense?
        if risk.days_until_season_end > 60 and risk.risk_level == 'critical':
            issues.append("Critical risk with 60+ days remaining seems inconsistent")
        
        await self._log_thought(
            thought_type="verification",
            summary=f"Proposal verification: {'✅ Passed' if verified else '⚠️ Issues found'}",
            detailed_reasoning={
                'verified': verified,
                'issues': issues,
                'proposal_id': proposal.id
            }
        )
        
        return {
            'verified': verified,
            'issues': issues
        }
