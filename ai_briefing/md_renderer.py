# ai_briefing/md_renderer.py
from typing import Dict, List

def render_md(data: Dict) -> str:
    title = data.get("title", "Briefing")
    date = data.get("date", "")
    lines: List[str] = [f"# {title}", "", f"> {date}", ""]
    topics = data.get("topics") or []
    for i, t in enumerate(topics, 1):
        headline = t.get("headline","").strip()
        lines.append(f"## {i}. {headline}")
        bullets = t.get("bullets") or []
        for b in bullets:
            lines.append(f"- {b}")
        links = t.get("links") or []
        if links:
            links_line = "  ".join(f"[来源]({u})" for u in dict.fromkeys(links))
            lines.append(f"\n{links_line}\n")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
