"""
Claude API Client.

Wrapper for Anthropic's Claude API for generating campaign copy.
This is a REAL integration, not a mock.
"""

from typing import Optional
import httpx

from app.config import get_settings

settings = get_settings()


class ClaudeClient:
    """Client for interacting with Claude API."""
    
    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
    
    async def generate(
        self, 
        prompt: str, 
        max_tokens: int = 1024,
        system: Optional[str] = None
    ) -> str:
        """
        Generate text using Claude API.
        
        Args:
            prompt: User message/prompt
            max_tokens: Maximum tokens in response
            system: Optional system prompt
            
        Returns:
            Generated text content
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        
        body = {
            "model": self.MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system:
            body["system"] = system
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.API_URL,
                headers=headers,
                json=body,
            )
            
            if response.status_code != 200:
                raise Exception(f"Claude API error: {response.status_code} - {response.text}")
            
            data = response.json()
            return data["content"][0]["text"]


# Singleton instance
claude = ClaudeClient()
