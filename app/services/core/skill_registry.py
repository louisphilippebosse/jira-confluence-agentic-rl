"""
Skill Registry - Discovers and manages available skills

Skills are modular capabilities that the AI agent can use.
Each skill has metadata (name, description) and instructions (SKILL.md).
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents a skill with metadata and content"""
    name: str
    description: str
    skill_path: Path
    instructions: str  # Full SKILL.md content
    metadata: Dict  # Additional frontmatter fields
    
    @property
    def references_dir(self) -> Optional[Path]:
        """Path to references directory if it exists"""
        ref_dir = self.skill_path / "references"
        return ref_dir if ref_dir.exists() else None
    
    @property
    def scripts_dir(self) -> Optional[Path]:
        """Path to scripts directory if it exists"""
        scripts_dir = self.skill_path / "scripts"
        return scripts_dir if scripts_dir.exists() else None
    
    @property
    def assets_dir(self) -> Optional[Path]:
        """Path to assets directory if it exists"""
        assets_dir = self.skill_path / "assets"
        return assets_dir if assets_dir.exists() else None


class SkillRegistry:
    """Registry of available skills"""
    
    def __init__(self, skills_directory: str = "./skills"):
        self.skills_directory = Path(skills_directory)
        self.skills: Dict[str, Skill] = {}
        self._load_skills()
    
    def _load_skills(self):
        """Discover and load all skills from the skills directory"""
        if not self.skills_directory.exists():
            logger.warning(f"Skills directory not found: {self.skills_directory}")
            return
        
        for skill_dir in self.skills_directory.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                logger.warning(f"Skipping {skill_dir.name} - no SKILL.md found")
                continue
            
            try:
                skill = self._load_skill(skill_dir, skill_md)
                self.skills[skill.name] = skill
                logger.info(f"✅ Loaded skill: {skill.name}")
            except Exception as e:
                logger.error(f"❌ Failed to load skill {skill_dir.name}: {e}")
    
    def _load_skill(self, skill_dir: Path, skill_md: Path) -> Skill:
        """Load a single skill from its SKILL.md"""
        content = skill_md.read_text(encoding='utf-8')
        
        # Parse frontmatter
        if not content.startswith('---'):
            raise ValueError("SKILL.md must start with YAML frontmatter")
        
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError("Invalid SKILL.md format")
        
        frontmatter_text = parts[1]
        instructions = parts[2].strip()
        
        frontmatter = yaml.safe_load(frontmatter_text)
        
        if 'name' not in frontmatter:
            raise ValueError("Missing 'name' in frontmatter")
        if 'description' not in frontmatter:
            raise ValueError("Missing 'description' in frontmatter")
        
        return Skill(
            name=frontmatter['name'],
            description=frontmatter['description'],
            skill_path=skill_dir,
            instructions=instructions,
            metadata=frontmatter
        )
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(name)
    
    def list_skills(self) -> List[Skill]:
        """Get all loaded skills"""
        return list(self.skills.values())
    
    def get_skills_metadata(self) -> List[Dict]:
        """
        Get lightweight metadata for all skills (for LLM context).
        Only returns name and description - not full instructions.
        """
        return [
            {
                "name": skill.name,
                "description": skill.description
            }
            for skill in self.skills.values()
        ]
    
    def find_relevant_skills(self, query: str, llm) -> List[Skill]:
        """
        Use LLM to determine which skills are relevant for a query.
        Returns list of skills that should be considered.
        """
        skills_metadata = self.get_skills_metadata()
        
        if not skills_metadata:
            logger.warning("No skills available")
            return []
        
        prompt = f"""User query: "{query}"

Available skills:
{yaml.dump(skills_metadata, default_flow_style=False)}

Which skills are relevant for answering this query? Consider:
- What data sources are needed?
- What operations are required?
- Are multiple skills needed (e.g., search + analyze)?

Return ONLY the skill names as a comma-separated list.
If no skills match, return "NONE".

Example responses:
- "jira-search"
- "jira-search, knowledge-graph-query"
- "confluence-search, knowledge-graph-query"
- "NONE"

Relevant skills:"""
        
        try:
            response = llm.invoke(prompt)
            result = response.content.strip()
            
            if result.upper() == "NONE":
                return []
            
            # Parse skill names
            skill_names = [name.strip() for name in result.split(',')]
            skills = [self.get_skill(name) for name in skill_names]
            skills = [s for s in skills if s is not None]  # Filter out None
            
            logger.info(f"🎯 Selected skills: {[s.name for s in skills]}")
            return skills
            
        except Exception as e:
            logger.error(f"Error finding relevant skills: {e}")
            return []


# Global instance
skill_registry = None


def get_skill_registry(skills_directory: str = "./skills") -> SkillRegistry:
    """Get or create the global skill registry"""
    global skill_registry
    if skill_registry is None:
        skill_registry = SkillRegistry(skills_directory)
    return skill_registry
