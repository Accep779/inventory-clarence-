import asyncio
import os
import sys

# Ensure backend acts as root
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.skill_loader import SkillLoader

async def main():
    print("🧠 Testing Market Scout Skill...")
    
    loader = SkillLoader()
    # Requesting 'market_scout'
    skills = loader.load_skills(["market_scout"])
    
    if not skills:
        print("❌ FAIL: Failed to load 'market_scout' skill.")
        return
        
    skill = skills[0]
    print(f"\n✅ Logic Loaded: {skill.name}")
    print(f"   Tools: {[t.__name__ for t in skill.tools]}")
    
    # Execute Tool
    try:
        scout_tool = next(t for t in skill.tools if t.__name__ == "check_competitor_prices")
        
        # Test Case 1: Expensive Item
        print("\n[1] Testing 'Winter Jacket'...")
        res1 = scout_tool("Winter Jacket")
        print(f"   Pricing: Min ${res1['market_min']} | Max ${res1['market_max']}")
        
        # Test Case 2: Cheap Item (Different hash)
        print("\n[2] Testing 'Socks'...")
        res2 = scout_tool("Socks")
        print(f"   Pricing: Min ${res2['market_min']} | Max ${res2['market_max']}")
        
        if res1['market_avg'] != res2['market_avg']:
            print("\n✅ Success: Different products returned different realistic mock prices.")
        else:
            print("\n❌ Fail: Prices were identical (Mock logic broken).")
            
    except StopIteration:
        print(f"❌ FAIL: 'check_competitor_prices' tool not found.")

if __name__ == "__main__":
    asyncio.run(main())
