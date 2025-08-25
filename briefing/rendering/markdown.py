
"""Render briefing to Markdown format."""

from typing import Dict, List

def render_md(data: Dict) -> str:
    """Render briefing object to Markdown."""
    title = data.get("title", "Briefing")
    date = data.get("date", "")
    lines: List[str] = [f"# {title}", "", f"> {date}", ""]
    
    topics = data.get("topics") or []
    for i, topic in enumerate(topics, 1):
        headline = topic.get("headline", "").strip()
        lines.append(f"## {i}. {headline}")
        lines.append("")
        
        bullets = topic.get("bullets") or []
        for bullet in bullets:
            # New structure: bullet is {text, url} object
            text = bullet.get("text", "")
            url = bullet.get("url", "")
            if url:
                lines.append(f"- [{text}]({url})")
            else:
                lines.append(f"- {text}")
        
        lines.append("")
    
    return "\n".join(lines).strip() + "\n"


