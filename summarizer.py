import os
import json
import requests
import datetime as dt
from typing import List, Dict, Any, Tuple, Optional
from utils import load_file, get_logger

from google import genai
from google.genai import types as gtypes

OLLAMA_ORIGIN = os.getenv("OLLAMA_ORIGIN", "http://ollama:11434")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
logger = get_logger(__name__)

def _mk_prompt(config: dict, bundles: List[dict]) -> str:
    system_txt = load_file(config["summarization"]["prompt_system"])
    template = load_file(config["summarization"]["prompt_template"])
    payload = {
        "briefing_title": config["briefing_title"],
        "bundles_json": json.dumps(bundles, ensure_ascii=False)
    }
    prompt = template
    for k, v in payload.items():
        prompt = prompt.replace("{{" + k + "}}", str(v))
    return system_txt.strip() + "\n\n" + prompt.strip()

def _call_gemini(model: str, text: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=model,
        contents=[text]
    )
    return resp.text

def _call_ollama(model: str, text: str) -> str:
    url = f"{OLLAMA_ORIGIN}/api/generate"
    data = {"model": model, "prompt": text, "stream": False}
    resp = requests.post(url, json=data, timeout=600)
    resp.raise_for_status()
    js = resp.json()
    return js.get("response", "")

def _split_json_and_md(raw: str) -> Tuple[dict, str]:
    raw = raw.strip()
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        raise ValueError("LLM output JSON not found.")
    json_str = raw[first_brace:last_brace+1]
    md = raw[last_brace+1:].strip()
    obj = json.loads(json_str)
    return obj, md

def generate_summary(bundles: List[dict], config: dict) -> Tuple[Optional[str], Optional[dict]]:
    if not bundles:
        logger.info("summarizer: empty bundles -> skip generation")
        return None, None

    prompt = _mk_prompt(config, bundles)
    provider = config["summarization"]["llm_provider"]

    if provider == "gemini":
        model = config["summarization"]["gemini_model"]
        out = _call_gemini(model, prompt)
    else:
        model = config["summarization"]["ollama_model"]
        out = _call_ollama(model, prompt)

    obj, md = _split_json_and_md(out)
    n = int(config["summarization"]["target_item_count"])
    if "topics" in obj:
        obj["topics"] = obj["topics"][:n]

    if not obj.get("topics"):
        logger.info("summarizer: empty topics -> skip generation")
        return None, None

    obj["title"] = config["briefing_title"]
    obj["date"] = dt.datetime.now(dt.timezone.utc).isoformat()
    md_full = f"# {obj['title']}\n\n> {obj['date']}\n\n{md}"

    logger.info("summarizer: generated topics=%d", len(obj["topics"]))
    return md_full, obj