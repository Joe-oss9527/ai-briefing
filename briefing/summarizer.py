# summarizer.py
import os, json, datetime as dt
from typing import List, Dict, Any
from briefing.utils import get_logger, load_file
from briefing.llm.registry import call_with_options as llm_call
from briefing.rendering.markdown import render_md
from briefing.output_validator import validate_briefing

logger = get_logger(__name__)

def _mk_prompt(bundles: List[Dict[str, Any]], cfg: dict) -> str:
    """Render prompt from YAML (system+task). `summarization.prompt_file` is required."""
    summ = cfg.get("summarization") or {}
    prompt_file = summ.get("prompt_file")
    if not prompt_file:
        raise ValueError("summarization.prompt_file is required")
    from briefing.rendering.prompt_loader import render_prompt
    title = cfg.get("briefing_title", "AI 简报")
    return render_prompt(title, bundles, prompt_file)

def _is_empty(obj: dict) -> bool:
    topics = (obj or {}).get("topics") or []
    return len(topics) == 0

def generate_summary(bundles: List[Dict[str, Any]], config: dict):
    if not bundles:
        logger.info("summarizer: no bundles -> skip")
        return None, None

    prompt = _mk_prompt(bundles, config)
    summ = config.get("summarization") or {}
    provider = (summ.get("llm_provider") or "gemini").lower()
    temperature = float(summ.get("temperature", 0.2))
    timeout = int(summ.get("timeout", 600))
    retries = int(summ.get("retries", 0))
    provider_options = summ.get("provider_options") or {}

    if provider == "gemini":
        model = summ.get("gemini_model")
    elif provider == "openai":
        model = summ.get("openai_model")
    else:
        raise ValueError(f"Unknown llm_provider={provider}")
    if not model:
        raise ValueError(f"Model not configured for provider={provider}. Set summarization.{provider}_model")

    text = llm_call(
        provider=provider,
        prompt=prompt,
        model=model,
        temperature=temperature,
        timeout=timeout,
        retries=retries,
        options=provider_options.get(provider) or provider_options
    )

    # Parse JSON only (strip code fences etc. defensively)
    raw = text.strip()
    try:
        if raw.startswith("```"):
            # attempt to slice the first {...} block
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                raw = raw[start:end+1]
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"LLM did not return valid JSON: {e}; raw_head={raw[:200]!r}") from e

    # Schema validation
    schema_path = os.path.join(os.path.dirname(__file__), "schemas", "briefing.schema.json")
    schema_str = load_file(schema_path)
    validate_briefing(obj, schema_str)

    if _is_empty(obj):
        logger.info("summarizer: empty topics after validation -> skip")
        return None, None

    # Ensure title/date
    obj["title"] = config.get("briefing_title", obj.get("title") or "AI Briefing")
    obj["date"] = dt.datetime.now(dt.timezone.utc).isoformat()

    # Render Markdown locally
    md = render_md(obj)
    logger.info("summarizer: ok topics=%d", len(obj.get("topics") or []))
    return md, obj
