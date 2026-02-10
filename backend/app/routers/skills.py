from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel

from app.services.skill_loader import SkillLoader
# In a real app, we might inject this dependency or use a singleton service
# For now, we instantiate on demand or use a cached instance if we had one.

router = APIRouter(
    prefix="/skills",
    tags=["Skills System"]
)

class SkillSchema(BaseModel):
    name: str
    description: str
    active: bool = True
    tool_count: int

@router.get("/", response_model=Dict[str, Any])
async def list_skills():
    """
    List all available skills (Observer capabilities).
    This allows the Frontend 'Skill Store' to display what the agent can do.
    """
    loader = SkillLoader()
    # In a real scenario, we'd scan the DIR every time or use a cache.
    # We'll explicitly look for our known skills for this MVP + scan others
    # For now, let's scan the directory dynamically as built in Phase 6.
    
    found_skills = []
    
    # We iterate the directory to find valid skill folders
    if loader.skills_dir.exists():
        for item in loader.skills_dir.iterdir():
            if item.is_dir():
                try:
                    # Try loading it to get metadata
                    loaded = loader.load_skills([item.name])
                    if loaded:
                        skill = loaded[0]
                        found_skills.append({
                            "name": skill.name,
                            "description": skill.description,
                            "active": True, # Default to true for now
                            "tool_count": len(skill.tools)
                        })
                except Exception as e:
                    print(f"Skipping broken skill {item.name}: {e}")
                    
    return {
        "skills": found_skills,
        "count": len(found_skills)
    }

@router.post("/{skill_name}/toggle")
async def toggle_skill(skill_name: str, active: bool):
    """
    Enable/Disable a specific skill.
    (Stub for future DB persistence of enabled/disabled state)
    """
    return {"status": "success", "skill": skill_name, "active": active}
