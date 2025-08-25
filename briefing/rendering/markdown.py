
"""Render briefing to Markdown format."""

from typing import Dict, List
from briefing.config.constants import DEFAULT_CONFIG

def render_md(data: Dict, config: Dict = None) -> str:
    """Render briefing object to Markdown.
    
    Args:
        data: Briefing data dictionary
        config: Configuration dict with language and labels settings
        
    Returns:
        Markdown formatted string
        
    Raises:
        ValueError: If data is not a valid dictionary
    """
    # Input validation
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data).__name__}")
    
    if config is None:
        config = DEFAULT_CONFIG
    
    # Get source link label from config
    source_label = config.get("labels", {}).get("source_link", "消息来源")
    
    # Validate and sanitize basic fields
    title = str(data.get("title", "Briefing")).strip() or "Briefing"
    date = str(data.get("date", "")).strip()
    
    lines: List[str] = [f"# {title}", "", f"> {date}", ""]
    
    topics = data.get("topics")
    if not isinstance(topics, list):
        topics = []
    
    for i, topic in enumerate(topics, 1):
        if not isinstance(topic, dict):
            continue  # Skip invalid topics
            
        headline = str(topic.get("headline", "")).strip()
        if not headline:
            headline = f"Topic {i}"  # Fallback for empty headlines
            
        lines.append(f"## {i}. {headline}")
        lines.append("")
        
        bullets = topic.get("bullets")
        if not isinstance(bullets, list):
            bullets = []
            
        for bullet in bullets:
            if not isinstance(bullet, dict):
                continue  # Skip invalid bullets
                
            text = str(bullet.get("text", "")).strip()
            url = str(bullet.get("url", "")).strip()
            
            if not text:
                continue  # Skip empty bullets
                
            # Basic URL validation
            if url and not (url.startswith(('http://', 'https://'))):
                url = ""  # Clear invalid URLs
                
            if url:
                lines.append(f"- {text} [{source_label}]({url})")
            else:
                lines.append(f"- {text}")
        
        lines.append("")
    
    return "\n".join(lines).strip() + "\n"


