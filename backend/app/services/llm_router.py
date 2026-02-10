# app/services/llm_router.py
"""
LLM Router Service
==================
Intelligent LLM router that selects optimal model for each task.

EXTRACTED FROM: Cephly architecture
"""

from typing import Dict, Any, Optional, List, Literal
import os
import io
import json
import base64
import logging
import threading
from datetime import datetime
from decimal import Decimal

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import google.generativeai as genai
import PIL.Image

import sqlalchemy
from sqlalchemy import select
from app.database import async_session_maker

from app.models import LLMUsageLog, Merchant

logger = logging.getLogger(__name__)

# Type definitions
TaskType = Literal[
    'liquidation_analysis',
    'strategy_generation',
    'email_copy',
    'sms_copy',
    'landing_page_copy',
    'category_extraction',
    'visual_clustering',
    'agent_chat'
]


class LLMRouterError(Exception):
    """Base exception for LLM Router errors."""
    pass


class ProviderError(LLMRouterError):
    """Raised when a provider fails after retries."""
    pass


class LLMRouter:
    """
    Intelligent LLM router that selects optimal model for each task.
    """
    
    def __init__(self):
        # Initialize keys from environment
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.google_key = os.getenv('GOOGLE_API_KEY')
        
        # Lazy client initialization
        self._anthropic_client: Optional[AsyncAnthropic] = None
        self._openai_client: Optional[AsyncOpenAI] = None
        self._gemini_model = None
        
        if self.google_key:
            genai.configure(api_key=self.google_key)
        
        # Model routing configuration
        self.routing_config = self._build_routing_config()
    
    @property
    def anthropic(self) -> AsyncAnthropic:
        if self._anthropic_client is None:
            if not self.anthropic_key:
                raise LLMRouterError("ANTHROPIC_API_KEY not configured")
            self._anthropic_client = AsyncAnthropic(api_key=self.anthropic_key)
        return self._anthropic_client
    
    @property
    def openai(self) -> AsyncOpenAI:
        if self._openai_client is None:
            if not self.openai_key:
                raise LLMRouterError("OPENAI_API_KEY not configured")
            self._openai_client = AsyncOpenAI(api_key=self.openai_key)
        return self._openai_client
    
    @property
    def gemini(self):
        if self._gemini_model is None:
            if not self.google_key:
                raise LLMRouterError("GOOGLE_API_KEY not configured")
            self._gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        return self._gemini_model
    
    def _build_routing_config(self) -> Dict[TaskType, Dict[str, Any]]:
        openai_fallback = {
            'provider': 'openai',
            'model': 'gpt-4o',
            'max_tokens': 4000,
            'temperature': 0.3,
            'cost_per_1m_input': 2.50,
            'cost_per_1m_output': 10.00
        }
        
        return {
            'liquidation_analysis': {
                'provider': 'anthropic',
                'model': 'claude-3-5-sonnet-20240620',
                'max_tokens': 4000,
                'temperature': 0.3,
                'cost_per_1m_input': 3.00,
                'cost_per_1m_output': 15.00,
                'fallbacks': [openai_fallback]
            },
            'strategy_generation': {
                'provider': 'anthropic',
                'model': 'claude-3-5-sonnet-20240620',
                'max_tokens': 4000,
                'temperature': 0.5,
                'cost_per_1m_input': 3.00,
                'cost_per_1m_output': 15.00,
                'fallbacks': [openai_fallback]
            },
            'email_copy': {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'max_tokens': 1500,
                'temperature': 0.8,
                'cost_per_1m_input': 0.15,
                'cost_per_1m_output': 0.60,
                'fallbacks': []
            },
            'sms_copy': {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'max_tokens': 200,
                'temperature': 0.8,
                'cost_per_1m_input': 0.15,
                'cost_per_1m_output': 0.60,
                'fallbacks': []
            },
            'category_extraction': {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'max_tokens': 300,
                'temperature': 0.1,
                'cost_per_1m_input': 0.15,
                'cost_per_1m_output': 0.60,
                'fallbacks': []
            },
            'visual_clustering': {
                'provider': 'google',
                'model': 'gemini-1.5-flash',
                'max_tokens': 2000,
                'temperature': 0.2,
                'cost_per_1m_input': 0.075,
                'cost_per_1m_output': 0.30,
                'fallbacks': []
            },
            'agent_chat': {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'max_tokens': 1000,
                'temperature': 0.7,
                'cost_per_1m_input': 0.15,
                'cost_per_1m_output': 0.60,
                'fallbacks': []
            }
        }
    
    async def complete(
        self,
        task_type: TaskType,
        system_prompt: str,
        user_prompt: str,
        merchant_id: Optional[str] = None,
        images: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if task_type not in self.routing_config:
            raise ValueError(f"Unknown task_type: {task_type}")
            
        # 0. BUDGET CHECK
        if merchant_id:
            async with async_session_maker() as session:
                res = await session.execute(
                    select(Merchant.monthly_llm_budget, Merchant.current_llm_spend)
                    .where(Merchant.id == merchant_id)
                )
                merchant_data = res.first()
                if merchant_data:
                    budget, spend = merchant_data
                    if spend >= budget:
                        logger.error(f"💰 [Budget] Merchant {merchant_id} exceeded LLM budget (${budget})")
                        raise LLMRouterError(f"Monthly LLM budget of ${budget} exceeded.")

        
        initial_config = self.routing_config[task_type]
        
        # Build execution chain: Primary -> Fallbacks -> Deterministic
        chain = [initial_config] + initial_config.get('fallbacks', [])
        
        start_time = datetime.utcnow()
        last_error = None
        
        for i, config in enumerate(chain):
            try:
                result = await self._call_provider(
                    provider=config['provider'],
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    images=images,
                    config=config
                )
                
                latency = (datetime.utcnow() - start_time).total_seconds()
                
                # Track usage
                self._track_usage(
                    merchant_id=merchant_id,
                    task_type=task_type,
                    provider=config['provider'],
                    model=result['model'],
                    input_tokens=result['tokens']['input'],
                    output_tokens=result['tokens']['output'],
                    cost=result['cost'],
                    latency=latency,
                    used_fallback=(i > 0),
                    metadata=metadata
                )
                
                # Update DB Spend
                if merchant_id:
                    await self._update_merchant_spend(merchant_id, result['cost'])
                
                return {
                    'content': result['content'],
                    'model': result['model'],
                    'provider': config['provider'],
                    'cost': result['cost'],
                    'latency': latency
                }
                
            except Exception as e:
                logger.warning(f"Provider {config['provider']} ({config['model']}) failed: {e}")
                last_error = e
                continue
        
        # If all providers fail, use deterministic fallback
        logger.error(f"All LLM providers failed for {task_type}. Last error: {last_error}")
        return self._deterministic_fallback(task_type, user_prompt)

    async def _update_merchant_spend(self, merchant_id: str, cost: float):
        try:
            async with async_session_maker() as session:
                from app.models import Merchant
                from sqlalchemy import update
                await session.execute(
                    update(Merchant)
                    .where(Merchant.id == merchant_id)
                    .values(current_llm_spend=Merchant.current_llm_spend + Decimal(str(cost)))
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update merchant spend: {e}")

    def _deterministic_fallback(self, task_type: str, user_prompt: str) -> Dict[str, Any]:
        """
        Final safety net when all AI fails. Returns hardcoded safe defaults.
        """
        logger.critical(f"⚠️ ENGAGING DETERMINISTIC FALLBACK for {task_type}")
        
        fallback_content = ""
        
        if task_type == 'strategy_generation':
            # Extract basic info if possible or return safe default
            fallback_content = json.dumps({
                "strategy_name": "Safety Default Sale",
                "discount_percentage": 0.10,
                "reasoning": "Global AI Outage - Applying safe conservative discount.",
                "confidence_score": 1.0
            })
        elif task_type == 'email_copy':
            fallback_content = "<h2>Clearance Sale</h2><p>We are having a sale on select items. Check our store for details.</p>"
        elif task_type == 'sms_copy':
            fallback_content = "Flash Sale Alert: Special discounts available now at our store. Link: {link}"
        elif task_type == 'agent_chat':
            fallback_content = json.dumps({
                "response": "I'm having trouble connecting to my creative brain right now. Please try again or create a new proposal.",
                "updated_proposal_data": {}
            })
        else:
            fallback_content = "Service temporarily degraded. Please try again later."
            
        return {
            'content': fallback_content,
            'model': 'deterministic-fallback',
            'provider': 'system',
            'cost': 0.0,
            'latency': 0.0
        }
    
    async def _call_provider(self, provider, system_prompt, user_prompt, images, config):
        if provider == 'anthropic':
            return await self._call_anthropic(system_prompt, user_prompt, config)
        elif provider == 'openai':
            return await self._call_openai(system_prompt, user_prompt, images, config)
        elif provider == 'google':
            return await self._call_google(system_prompt, user_prompt, images, config)
        raise ValueError(f"Unknown provider: {provider}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _call_anthropic(self, system_prompt, user_prompt, config):
        response = await self.anthropic.messages.create(
            model=config['model'],
            max_tokens=config['max_tokens'],
            temperature=config['temperature'],
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        cost = self._calculate_cost(response.usage.input_tokens, response.usage.output_tokens, 
                                   config['cost_per_1m_input'], config['cost_per_1m_output'])
        return {
            'content': response.content[0].text,
            'model': config['model'],
            'tokens': {'input': response.usage.input_tokens, 'output': response.usage.output_tokens},
            'cost': cost
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _call_openai(self, system_prompt, user_prompt, images, config):
        messages = [{"role": "system", "content": system_prompt}]
        if images:
            content = [{"type": "text", "text": user_prompt}]
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": img}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_prompt})
            
        response = await self.openai.chat.completions.create(
            model=config['model'],
            max_tokens=config['max_tokens'],
            temperature=config['temperature'],
            messages=messages
        )
        cost = self._calculate_cost(response.usage.prompt_tokens, response.usage.completion_tokens,
                                   config['cost_per_1m_input'], config['cost_per_1m_output'])
        return {
            'content': response.choices[0].message.content,
            'model': config['model'],
            'tokens': {'input': response.usage.prompt_tokens, 'output': response.usage.completion_tokens},
            'cost': cost
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _call_google(self, system_prompt, user_prompt, images, config):
        prompt_parts = [f"{system_prompt}\n\n{user_prompt}"]
        if images:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for img_url in images:
                    async with session.get(img_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            prompt_parts.append(PIL.Image.open(io.BytesIO(img_data)))
        
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.gemini.generate_content(
            prompt_parts, 
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
        ))
        
        # Estimate tokens for Gemini (simplified for Multi)
        input_tokens = len(prompt_parts[0]) // 4
        if images: input_tokens += len(images) * 258
        output_tokens = len(response.text) // 4
        
        cost = self._calculate_cost(input_tokens, output_tokens, config['cost_per_1m_input'], config['cost_per_1m_output'])
        return {
            'content': response.text,
            'model': config['model'],
            'tokens': {'input': input_tokens, 'output': output_tokens},
            'cost': cost
        }

    def _calculate_cost(self, input_t, output_t, input_p, output_p):
        return (input_t / 1_000_000 * input_p) + (output_t / 1_000_000 * output_p)

    def _track_usage(self, **kwargs):
        thread = threading.Thread(target=self._persist_usage, kwargs=kwargs, daemon=True)
        thread.start()

    def _persist_usage(self, **kwargs):
        import asyncio
        async def save():
            async with async_session_maker() as session:
                log = LLMUsageLog(
                    merchant_id=kwargs.get('merchant_id'),
                    task_type=kwargs.get('task_type'),
                    provider=kwargs.get('provider'),
                    model=kwargs.get('model'),
                    input_tokens=kwargs.get('input_tokens'),
                    output_tokens=kwargs.get('output_tokens'),
                    cost_usd=Decimal(str(kwargs.get('cost'))),
                    latency=kwargs.get('latency'),
                    used_fallback=kwargs.get('used_fallback', False),
                    metadata_json=kwargs.get('metadata')
                )
                session.add(log)
                await session.commit()
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(save())
            loop.close()
        except Exception as e:
            logger.error(f"Failed to persist LLM log: {e}")
