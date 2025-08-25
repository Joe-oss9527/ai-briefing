import os
import json
import datetime as dt
from typing import List, Dict, Any, Optional, Tuple

from briefing.utils import get_logger
from briefing.llm.registry import call_with_schema
from briefing.rendering.markdown import render_md

logger = get_logger(__name__)

def _mk_prompt(bundles: List[Dict[str, Any]], cfg: dict) -> str:
    """Render prompt from YAML template."""
    summ = cfg.get("summarization", {})
    prompt_file = summ.get("prompt_file")
    if not prompt_file:
        raise ValueError("summarization.prompt_file required")
    
    from briefing.rendering.prompt_loader import render_prompt
    title = cfg.get("briefing_title", "AI 简报")
    return render_prompt(title, bundles, prompt_file)

def generate_summary(bundles: List[Dict[str, Any]], 
                    config: dict) -> Tuple[Optional[str], Optional[Dict]]:
    """Generate summary using structured outputs."""
    if not bundles:
        logger.info("No bundles to summarize")
        return None, None
    
    # Load schema
    schema_path = os.path.join(os.path.dirname(__file__), "schemas", "briefing.schema.json")
    with open(schema_path) as f:
        schema = json.load(f)
    
    # Get config
    summ = config.get("summarization", {})
    provider = summ.get("llm_provider", "gemini").lower()
    
    if provider == "gemini":
        model = summ.get("gemini_model", "gemini-2.0-flash-exp")
    elif provider == "openai":
        model = summ.get("openai_model", "gpt-4o-2024-08-06")
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    # Call LLM with schema
    obj = call_with_schema(
        provider=provider,
        prompt=_mk_prompt(bundles, config),
        model=model,
        schema=schema,
        temperature=float(summ.get("temperature", 0.2)),
        timeout=int(summ.get("timeout", 600)),
        retries=int(summ.get("retries", 0)),
        options=summ.get("provider_options", {}).get(provider)
    )
    
    # Check if empty
    if not obj.get("topics"):
        logger.info("Empty topics")
        return None, None
    
    # Set metadata
    obj["title"] = config.get("briefing_title", obj.get("title", "AI Briefing"))
    obj["date"] = obj.get("date", dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'))
    
    # Extract rendering config from main config
    rendering_config = config.get("rendering", {})
    
    # Render
    md = render_md(obj, rendering_config)
    logger.info("Generated %d topics", len(obj["topics"]))
    
    return md, obj
