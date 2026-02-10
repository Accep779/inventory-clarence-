# Skills System: Technical Specification

## 1. Skill Folder Structure
Each skill must reside in `backend/app/skills/<skill_name>/`.

### `SKILL.md` (Required)
The "Manual" for the AI. Frontmatter defines metadata.

```markdown
---
name: inventory_checker
description: Check stock levels.
system_prompt_priority: 10
---
# Inventory Checker

Use this skill when the user asks about product stock.
If stock is low (<5), suggesting a similar product.
```

### `tools.py` (Required)
The Python implementation. Must export a `tools` list or decorated functions.

```python
from app.services.skill_loader import skill_tool

@skill_tool
def check_stock(product_id: str) -> int:
    """Returns the current stock level."""
    return 42
```

## 2. The `SkillLoader` Service
Path: `backend/app/services/skill_loader.py`

```python
class Skill:
    name: str
    path: Path
    description: str
    system_prompt: str
    tools: List[Callable]

class SkillLoader:
    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)

    def load_skill(self, skill_name: str) -> Skill:
        # 1. Read SKILL.md frontmatter & content
        # 2. Import tools.py using importlib
        # 3. Return Skill object
        pass
        
    def list_available_skills(self) -> List[str]:
        # Returns list of folder names in skills_dir
        pass
```

## 3. Tool Decorator
A simple decorator to mark functions that should be exposed to the LLM.

```python
_REGISTRY = {}

def skill_tool(func):
    _REGISTRY[func.__name__] = func
    return func
```
