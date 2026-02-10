import os
import importlib.util
from typing import List, Dict, Callable
from pathlib import Path

class Skill:
    def __init__(self, name: str, description: str, system_prompt: str, tools: List[Callable]):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools

class SkillLoader:
    """
    Dynamic Skill Loader.
    Reads SKILL.md and tools.py from app/skills/<skill_name>/
    """
    
    def __init__(self, skills_dir: str = None):
        if not skills_dir:
            # Default to backend/app/skills
            base_dir = Path(__file__).parent.parent
            self.skills_dir = base_dir / "skills"
        else:
            self.skills_dir = Path(skills_dir)
            
    def load_skills(self, skill_names: List[str]) -> List[Skill]:
        loaded = []
        for name in skill_names:
            try:
                skill = self._load_single_skill(name)
                loaded.append(skill)
            except Exception as e:
                print(f"❌ [Skills] Failed to load '{name}': {e}")
        return loaded

    def _load_single_skill(self, name: str) -> Skill:
        skill_path = self.skills_dir / name
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill directory not found: {skill_path}")
            
        # 1. Read SKILL.md (System Prompt + Metadata)
        md_path = skill_path / "SKILL.md"
        if not md_path.exists():
             raise FileNotFoundError(f"SKILL.md missing for {name}")
             
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse Frontmatter (Simple manual parse for now to avoid yaml dependency if possible, else use yaml)
        # Assuming standard --- format
        import yaml
        if content.startswith("---"):
            try:
                frontmatter_end = content.find("---", 3)
                frontmatter = content[3:frontmatter_end]
                metadata = yaml.safe_load(frontmatter)
                description = metadata.get("description", "")
                
                # System Prompt is everything after frontmatter
                system_prompt = content[frontmatter_end+3:].strip()
            except Exception as e:
                print(f"⚠️ [Skills] YAML parse error for {name}: {e}")
                description = "Error parsing metadata"
                system_prompt = content
        else:
            description = "No metadata"
            system_prompt = content

        # 2. Load Tools (tools.py)
        tools_path = skill_path / "tools.py"
        tools = []
        if tools_path.exists():
            spec = importlib.util.spec_from_file_location(f"skills.{name}", tools_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find decorated functions or 'exports' list
            # Convention: Look for functions with _is_skill_tool = True
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and getattr(attr, "_is_skill_tool", False):
                    tools.append(attr)
                    
        return Skill(name, description, system_prompt, tools)

# Decorator
def skill_tool(func):
    func._is_skill_tool = True
    return func
