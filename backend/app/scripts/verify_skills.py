import asyncio
import os
import sys

# Ensure backend acts as root
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.skill_loader import SkillLoader

async def main():
    print("🧠 Testing Skills System Extensibility...")
    
    loader = SkillLoader()
    # Requesting a skill we just created ('math')
    skills = loader.load_skills(["math", "echo"])
    
    if len(skills) != 2:
        print(f"❌ FAIL: Expected 2 skills, got {len(skills)}")
        # Print loaded names for debugging
        print(f"   Loaded: {[s.name for s in skills]}")
        return
        
    # [FIX] Look for 'math' (folder name), not 'math_wizard' (frontmatter name)
    try:
        math_skill = next(s for s in skills if s.name == "math")
    except StopIteration:
        print(f"❌ FAIL: 'math' skill not found in {[s.name for s in skills]}")
        return
    
    print(f"\n✅ Logic Loaded: {math_skill.name}")
    print(f"   Description: {math_skill.description}")
    
    # Execute Math Tool
    try:
        add_func = next(t for t in math_skill.tools if t.__name__ == "add_numbers")
        result = add_func(10, 5)
        
        if result == 15:
             print(f"   ✅ Math Execution Success (10+5): {result}")
        else:
             print(f"   ❌ Math Execution Failed. Got: {result}")
    except StopIteration:
        print(f"❌ FAIL: 'add_numbers' tool not found. Tools: {[t.__name__ for t in math_skill.tools]}")

if __name__ == "__main__":
    asyncio.run(main())
