# ai_briefing/prompt_loader.py
import json, yaml
from jinja2 import Environment

def render_prompt(briefing_title: str, bundles, prompt_file: str) -> str:
    with open(prompt_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    bundles_json = json.dumps(bundles, ensure_ascii=False, indent=2)
    sys_t = env.from_string(data.get("system", ""))
    task_t = env.from_string(data.get("task", ""))
    sys_part = sys_t.render(briefing_title=briefing_title, bundles_json=bundles_json)
    task_part = task_t.render(briefing_title=briefing_title, bundles_json=bundles_json)
    return (sys_part + "\n\n" + task_part).strip() + "\n"
