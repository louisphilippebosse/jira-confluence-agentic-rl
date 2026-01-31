#!/usr/bin/env python3
"""
Skill Initializer - Creates a new skill template

Usage:
    python scripts/init_skill.py <skill-name> --path <output-directory>

Example:
    python scripts/init_skill.py jira-search --path skills/
"""

import sys
import argparse
from pathlib import Path


def init_skill(skill_name: str, output_path: str = "."):
    """
    Initialize a new skill with template structure.
    
    Args:
        skill_name: Name of the skill (hyphen-case)
        output_path: Directory where skill folder will be created
    """
    # Validate skill name
    if not skill_name.replace('-', '').replace('_', '').isalnum():
        print(f"❌ Error: Skill name '{skill_name}' must contain only letters, numbers, and hyphens")
        return False
    
    # Create skill directory
    output_dir = Path(output_path).resolve()
    skill_dir = output_dir / skill_name
    
    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        return False
    
    print(f"📁 Creating skill directory: {skill_dir}")
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    # Create SKILL.md with template
    skill_md_content = f"""---
name: {skill_name}
description: TODO - Describe what this skill does and when to use it. This is the PRIMARY triggering mechanism.
---

# {skill_name.replace('-', ' ').title()}

TODO: Add detailed instructions for using this skill.

## Overview

TODO: Explain what this skill does.

## Usage

TODO: Explain how to use this skill.

## Examples

TODO: Provide examples of using this skill.
"""
    
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md_content)
    print(f"  ✅ Created SKILL.md")
    
    # Create example directories
    (skill_dir / "scripts").mkdir(exist_ok=True)
    (skill_dir / "scripts" / "example_script.py").write_text(
        "#!/usr/bin/env python3\n# TODO: Add executable scripts here\n"
    )
    print(f"  ✅ Created scripts/ directory with example")
    
    (skill_dir / "references").mkdir(exist_ok=True)
    (skill_dir / "references" / "example_reference.md").write_text(
        "# Example Reference\n\nTODO: Add reference documentation here\n"
    )
    print(f"  ✅ Created references/ directory with example")
    
    (skill_dir / "assets").mkdir(exist_ok=True)
    (skill_dir / "assets" / "README.md").write_text(
        "# Assets\n\nTODO: Add templates, images, or other assets here\n"
    )
    print(f"  ✅ Created assets/ directory with example")
    
    print(f"\n✅ Successfully initialized skill: {skill_name}")
    print(f"   Location: {skill_dir}")
    print(f"\n📝 Next steps:")
    print(f"   1. Edit {skill_dir / 'SKILL.md'} with instructions")
    print(f"   2. Add any scripts, references, or assets needed")
    print(f"   3. Run: python scripts/package_skill.py {skill_dir}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Initialize a new skill with template structure"
    )
    parser.add_argument(
        "skill_name",
        help="Name of the skill (use hyphen-case, e.g., jira-search)"
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Output directory for the skill folder (default: current directory)"
    )
    
    args = parser.parse_args()
    
    success = init_skill(args.skill_name, args.path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
