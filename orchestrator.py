import os
import argparse
import time
import yaml
import uuid
import requests
from typing import Dict, Any, List

from adapters import twitter_list_adapter, rss_adapter, reddit_adapter, hackernews_adapter
from pipeline import run_processing_pipeline
from summarizer import generate_summary
from publisher import maybe_publish_telegram, maybe_github_backup
from utils import write_output, validate_config, wait_for_service, get_logger

logger = get_logger(__name__)

def _wait_infra(source_type=None):
    """Wait for infrastructure services to be ready."""
    tei = os.getenv("TEI_ORIGIN", "http://tei:80") + "/health"
    ollama = os.getenv("OLLAMA_ORIGIN", "http://ollama:11434") + "/api/tags"
    
    # Only check RSSHub if actually needed
    if source_type == "twitter_list":
        rsshub = os.getenv("RSSHUB_ORIGIN", "http://rsshub:1200") + "/healthz"
        wait_for_service(rsshub)
    
    # TEI and Ollama are always critical
    wait_for_service(tei)
    wait_for_service(ollama)

def _fetch_items(source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch items from configured source."""
    t = source_cfg["type"]
    if t == "twitter_list":
        return twitter_list_adapter.fetch(source_cfg)
    elif t == "rss":
        return rss_adapter.fetch(source_cfg)
    elif t == "reddit":
        return reddit_adapter.fetch(source_cfg)
    elif t == "hackernews":
        return hackernews_adapter.fetch(source_cfg)
    else:
        raise ValueError(f"Unknown source type: {t}")

def main():
    parser = argparse.ArgumentParser(description="Run a briefing generation task.")
    parser.add_argument('--config', type=str, required=True, help="Path to the briefing config YAML file.")
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:8]
    logger.info("=== run start id=%s ===", run_id)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    validate_config(cfg)
    briefing_id = cfg["briefing_id"]
    source_type = cfg["source"]["type"]
    logger.info("config loaded briefing_id=%s title=%s source=%s", briefing_id, cfg["briefing_title"], source_type)

    _wait_infra(source_type)

    t0 = time.monotonic()
    raw_items = _fetch_items(cfg["source"])
    logger.info("fetched items=%d took_ms=%d", len(raw_items), int((time.monotonic()-t0)*1000))

    t1 = time.monotonic()
    bundles = run_processing_pipeline(raw_items, cfg["processing"])
    logger.info("processed bundles=%d took_ms=%d", len(bundles), int((time.monotonic()-t1)*1000))

    t2 = time.monotonic()
    md, js = generate_summary(bundles, cfg)
    logger.info("summarized took_ms=%d", int((time.monotonic()-t2)*1000))

    if md is None or js is None:
        logger.info("empty briefing -> skip output & publish")
        logger.info("=== run end id=%s (empty) ===", run_id)
        return

    out_dir = cfg["output"]["dir"]
    write_output(md, js, cfg["output"])
    logger.info("output written dir=%s", out_dir)

    try:
        maybe_publish_telegram(md, cfg["output"])
    except Exception as e:
        logger.error("telegram publish failed: %s", e)

    try:
        maybe_github_backup(out_dir, cfg["output"], briefing_id, run_id)
    except Exception as e:
        logger.error("github backup failed: %s", e)

    logger.info("=== run end id=%s ===", run_id)

if __name__ == "__main__":
    main()