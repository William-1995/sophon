#!/usr/bin/env python3
"""Return exposed skills (name + description) for capabilities inquiry."""
import json
import sys


def main() -> None:
    params = json.loads(sys.stdin.read())
    try:
        from config import get_config
        from core.skill_loader import get_skills_brief
        brief = get_skills_brief()
        lines = [f"- **{s['skill_name']}**: {s['skill_description']}" for s in brief]
        text = "Available capabilities:\n\n" + "\n".join(lines) if lines else "No capabilities configured."
        print(json.dumps({"result": text, "observation": text, "answer": text}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
