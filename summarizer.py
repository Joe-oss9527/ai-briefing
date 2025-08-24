# summarizer.py
import os, json, datetime as dt
from typing import List, Dict, Any
from utils import get_logger, load_file
from ai_briefing.llm_adapters import call_with_options as llm_call
from ai_briefing.md_renderer import render_md
from ai_briefing.output_validator import validate_briefing

logger = get_logger(__name__)

def _mk_prompt(bundles: List[Dict[str, Any]], cfg: dict) -> str:
    """Render prompt from YAML (system+task). `summarization.prompt_file` is required."""
    briefing_title = cfg.get("briefing_title", "AI 简报")
    summ = cfg.get("summarization") or {}
    prompt_file = summ.get("prompt_file")
    if not prompt_file:
        raise ValueError("summarization.prompt_file is required")
    from ai_briefing.prompt_loader import render_prompt
    return render_prompt(briefing_title, bundles, prompt_file)

    # Fallback: legacy system/template
    from utils import load_file
    sys_path = summ.get("prompt_file")
    tmpl_path = summ.get("prompt_file")
    sys_prompt = load_file(sys_path) if sys_path else ""
    tmpl = load_file(tmpl_path) if tmpl_path else ""
    return f"{sys_prompt}

" + tmpl.replace("{{briefing_title}}", briefing_title).replace("{{bundles_json}}", bundles_json)

def _is_empty(obj: dict) -> bool:
    topics = (obj or {}).get("topics") or []
    return len(topics) == 0

def generate_summary(bundles: List[Dict[str, Any]], config: dict):
    if not bundles:
        logger.info("summarizer: no bundles -> skip")
        return None, None

    prompt = _mk_prompt(bundles, config)
    prov = (config["summarization"].get("llm_provider") or "gemini").lower()
    model = config["summarization"].get(f"{prov}_model")

    logger.info("summarizer: provider=%s model=%s", prov, model)
        # Gather runtime options
    summ = config.get("summarization") or {}
    temperature = float(summ.get("temperature", 0.2))
    timeout = int(summ.get("timeout", 600))
    retries = int(summ.get("retries", 0))
    provider_options = (summ.get("provider_options") or {}).get(prov, {}) if isinstance(summ.get("provider_options"), dict) else (summ.get("provider_options") or {})
    raw = llm_call(prov, prompt, model=model, temperature=temperature, timeout=timeout, retries=retries, options=provider_options)


    # Expect JSON only
    try:
        obj = json.loads(raw)
    except Exception:
        # Try to salvage JSON between first { ... } block
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            obj = json.loads(raw[start:end])
        except Exception as e:
            logger.error("summarizer: JSON parse failed: %s", e)
            raise

    # Validate against schema
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    schema_path = base_dir / "schemas" / "briefing.schema.json"
    schema_str = schema_path.read_text(encoding="utf-8")
    validate_briefing(obj, schema_str)

    # Enforce max topics
    n = int(config["summarization"].get("target_item_count", 10))
    if "topics" in obj:
        obj["topics"] = (obj["topics"] or [])[:n]

    if _is_empty(obj):
        logger.info("summarizer: empty topics after validation -> skip")
        return None, None

    # Ensure title/date
    obj["title"] = config.get("briefing_title", obj.get("title") or "AI Briefing")
    obj["date"] = dt.datetime.now(dt.timezone.utc).isoformat()

    # Render Markdown locally
    md = render_md(obj)
    logger.info("summarizer: ok topics=%d", len(obj["topics"]))
    return md, obj
