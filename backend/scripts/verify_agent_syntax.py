import sys
import os
import asyncio

sys.path.append(os.getcwd())

async def check_syntax():
    print("🔍 Checking Agent Syntax...")
    
    try:
        print("  - Checking Observer...")
        from app.agents.observer import ObserverAgent
        print("  ✅ Observer OK")
        
        print("  - Checking Execution...")
        from app.agents.execution import ExecutionAgent
        print("  ✅ Execution OK")
        
        print("  - Checking Matchmaker...")
        from app.agents.matchmaker import MatchmakerAgent
        print("  ✅ Matchmaker OK")
        
        print("  - Checking Reactivation...")
        from app.agents.reactivation import ReactivationAgent
        print("  ✅ Reactivation OK")
        
        print("  - Checking Seasonal...")
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        print("  ✅ Seasonal OK")
        
        print("\n✨ All Agents Syntax Verified.")
        
    except Exception as e:
        print(f"\n❌ Syntax/Import Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_syntax())
