# app/services/scraper.py
"""
Store Scraper Service
=====================
Scrapes merchant store URLs to extract brand context for Store DNA.
Gathers homepage metadata, about page content, and brand signals.
"""

import logging
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class StoreScraperService:
    """
    Scrapes merchant store homepage and about page for brand context.
    Used during onboarding and for Store DNA enrichment.
    """
    
    # Common about page paths for Shopify stores
    ABOUT_PAGE_PATHS = [
        "/pages/about",
        "/pages/about-us", 
        "/pages/our-story",
        "/about",
        "/about-us",
    ]
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.router = LLMRouter()
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CephlyBot/1.0 (Store Intelligence; contact@cephly.com)"
            }
        )

    async def scrape_store(self, store_url: str) -> Dict[str, Any]:
        """
        Scrapes:
        - Homepage: title, meta description, OG tags
        - About page: /pages/about, /pages/about-us, /about
        - Returns structured data for DNA enrichment
        """
        logger.info(f"🔍 Starting store scrape for: {store_url}")
        
        result = {
            "store_url": store_url,
            "scraped_at": datetime.utcnow().isoformat(),
            "homepage_meta": {},
            "about_content": None,
            "social_links": [],
            "errors": []
        }
        
        try:
            # Normalize URL
            if not store_url.startswith(('http://', 'https://')):
                store_url = f"https://{store_url}"
            
            # Scrape homepage
            homepage_data = await self._scrape_homepage(store_url)
            result["homepage_meta"] = homepage_data.get("meta", {})
            result["social_links"] = homepage_data.get("social_links", [])
            if homepage_data.get("error"):
                result["errors"].append(f"Homepage: {homepage_data['error']}")
            
            # Scrape about page
            about_data = await self._scrape_about_page(store_url)
            result["about_content"] = about_data.get("content")
            if about_data.get("error"):
                result["errors"].append(f"About page: {about_data['error']}")
            
            logger.info(f"✅ Store scrape complete for {store_url}")
            
        except Exception as e:
            logger.error(f"Store scrape failed: {e}")
            result["errors"].append(str(e))
        
        finally:
            await self.client.aclose()
        
        return result

    async def _scrape_homepage(self, url: str) -> Dict[str, Any]:
        """Scrape homepage for metadata and social links."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            meta = {
                "title": self._get_title(soup),
                "description": self._get_meta_content(soup, "description"),
                "og_title": self._get_meta_content(soup, "og:title"),
                "og_description": self._get_meta_content(soup, "og:description"),
                "og_image": self._get_meta_content(soup, "og:image"),
                "og_type": self._get_meta_content(soup, "og:type"),
            }
            
            social_links = self._extract_social_links(soup)
            
            return {"meta": meta, "social_links": social_links}
            
        except httpx.HTTPError as e:
            return {"error": str(e), "meta": {}, "social_links": []}
        except Exception as e:
            return {"error": str(e), "meta": {}, "social_links": []}

    async def _scrape_about_page(self, base_url: str) -> Dict[str, Any]:
        """Try to find and scrape about page content."""
        for path in self.ABOUT_PAGE_PATHS:
            about_url = urljoin(base_url, path)
            try:
                response = await self.client.get(about_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    content = self._extract_main_content(soup)
                    if content and len(content) > 100:
                        return {"content": content, "found_at": path}
            except:
                continue
        
        return {"error": "No about page found", "content": None}

    def _get_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        title_tag = soup.find('title')
        return title_tag.get_text(strip=True) if title_tag else None

    def _get_meta_content(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        """Extract meta tag content by name or property."""
        # Try name attribute
        tag = soup.find('meta', attrs={'name': name})
        if tag and tag.get('content'):
            return tag['content']
        
        # Try property attribute (for OG tags)
        tag = soup.find('meta', attrs={'property': name})
        if tag and tag.get('content'):
            return tag['content']
        
        return None

    def _extract_social_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract social media links from page."""
        social_domains = [
            'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
            'tiktok.com', 'pinterest.com', 'linkedin.com', 'youtube.com'
        ]
        
        links = []
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            for domain in social_domains:
                if domain in href:
                    if href not in links:
                        links.append(href)
                    break
        
        return links

    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main text content from a page."""
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Try to find main content area
        main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|page'))
        
        if main:
            text = main.get_text(separator=' ', strip=True)
        else:
            body = soup.find('body')
            text = body.get_text(separator=' ', strip=True) if body else ""
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit to reasonable length
        return text[:5000] if text else None

    async def extract_brand_signals(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses LLM to extract structured brand signals from scraped content.
        Returns brand tone, values, target customer, etc.
        """
        # Combine available context
        context_parts = []
        
        meta = scraped_data.get("homepage_meta", {})
        if meta.get("title"):
            context_parts.append(f"Store Title: {meta['title']}")
        if meta.get("description"):
            context_parts.append(f"Description: {meta['description']}")
        if meta.get("og_description"):
            context_parts.append(f"OG Description: {meta['og_description']}")
        
        if scraped_data.get("about_content"):
            context_parts.append(f"About Page:\n{scraped_data['about_content'][:2000]}")
        
        if not context_parts:
            return {"error": "No content to analyze"}
        
        context = "\n\n".join(context_parts)
        
        system_prompt = """You are Cephly's Brand Analyst. Analyze the provided store content to extract brand identity signals.
Respond in STRICT JSON format:
{
    "brand_tone": "e.g. Minimalist, Luxury, Playful, Professional, Edgy",
    "industry_type": "e.g. Fashion, Home Decor, Electronics, Beauty, Outdoor",
    "target_customer": "Brief description of ideal customer",
    "brand_values": ["Value1", "Value2", "Value3"],
    "communication_style": "e.g. Formal, Casual, Inspirational, Data-driven",
    "price_positioning": "e.g. Budget, Mid-range, Premium, Luxury"
}"""
        
        try:
            llm_res = await self.router.complete(
                task_type='brand_analysis',
                system_prompt=system_prompt,
                user_prompt=context,
                merchant_id=self.merchant_id
            )
            
            import json
            signals = json.loads(llm_res['content'])
            return signals
            
        except Exception as e:
            logger.error(f"Brand signal extraction failed: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
