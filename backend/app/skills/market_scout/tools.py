from app.services.skill_loader import skill_tool
import random
import hashlib

@skill_tool
def check_competitor_prices(product_name: str) -> dict:
    """
    Searches detailed competitor pricing for a given product.
    Returns structured data about market rates.
    """
    print(f"🔍 [Market Scout] Searching competitor prices for: '{product_name}'...")
    
    # [MOCK LOGIC]
    # Generate deterministic "fake" data based on product name hash
    # This allows test consistency (same input = same output)
    seed = int(hashlib.md5(product_name.encode()).hexdigest(), 16)
    random.seed(seed)
    
    base_price = random.uniform(20.0, 150.0)
    variance = random.uniform(0.05, 0.20)
    
    market_min = round(base_price * (1 - variance), 2)
    market_max = round(base_price * (1 + variance), 2)
    market_avg = round((market_min + market_max) / 2, 2)
    
    competitors = ["Amazon", "Walmart", "eBay", "Target"]
    top_competitor = random.choice(competitors)
    
    result = {
        "status": "success",
        "product_query": product_name,
        "currency": "USD",
        "market_min": market_min,
        "market_max": market_max,
        "market_avg": market_avg,
        "top_competitor": top_competitor,
        "competitor_price": round(random.uniform(market_min, market_max), 2),
        "source": "Mock (SerpApi Stub)"
    }
    
    print(f"   ✅ Found data: Avg ${market_avg} (Min ${market_min} - Max ${market_max})")
    return result
