
import os
import argparse
import time
import yaml
import uuid
import json
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from briefing.sources import twitter_list_adapter, rss_adapter, reddit_adapter, hackernews_adapter
from briefing.pipeline import run_processing_pipeline
from briefing.summarizer import generate_summary
from briefing.pipeline_multistep import compute_metrics, run_multistage_pipeline
from briefing.publisher import maybe_publish_telegram, maybe_briefing_archive
from briefing.rendering.markdown import render_md
from briefing.utils import write_output, validate_config, wait_for_service, get_logger

logger = get_logger(__name__)

def _wait_infra(source_type=None):
    """Wait for infrastructure services to be ready."""
    tei = os.getenv("TEI_ORIGIN", "http://tei:3000") + "/health"
    
    # Only check RSSHub if actually needed
    if source_type == "twitter_list":
        rsshub = os.getenv("RSSHUB_ORIGIN", "http://rsshub:1200") + "/healthz"
        wait_for_service(rsshub)
    
    # TEI is critical
    wait_for_service(tei)
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

def _apply_overrides(cfg: Dict[str, Any], overrides: Optional[Dict[str, Optional[bool]]]) -> None:
    if not overrides:
        return

    processing = cfg.setdefault("processing", {})
    if overrides.get("multi_stage") is not None:
        processing["multi_stage"] = overrides["multi_stage"]
    if overrides.get("agentic_section") is not None:
        processing["agentic_section"] = overrides["agentic_section"]
    if overrides.get("brief_lite") is not None:
        processing["brief_lite"] = overrides["brief_lite"]


def _execute_pipeline(cfg: Dict[str, Any], run_id: str, overrides: Optional[Dict[str, Optional[bool]]] = None) -> None:
    """Execute the core briefing pipeline with given configuration."""
    briefing_id = cfg["briefing_id"]
    source_type = cfg["source"]["type"]
    logger.info("config loaded briefing_id=%s title=%s source=%s", briefing_id, cfg["briefing_title"], source_type)

    _apply_overrides(cfg, overrides)

    _wait_infra(source_type)

    t0 = time.monotonic()
    raw_items = _fetch_items(cfg["source"])
    logger.info("fetched items=%d took_ms=%d", len(raw_items), int((time.monotonic()-t0)*1000))

    t1 = time.monotonic()
    bundles = run_processing_pipeline(raw_items, cfg["processing"])
    logger.info("processed bundles=%d took_ms=%d", len(bundles), int((time.monotonic()-t1)*1000))

    use_multi_stage = bool(cfg.get("processing", {}).get("multi_stage"))

    if use_multi_stage:
        t2 = time.monotonic()
        briefing_obj, state = run_multistage_pipeline(
            bundles,
            cfg,
            briefing_id=briefing_id,
            output_root=Path(cfg["output"]["dir"]),
        )
        js = briefing_obj.model_dump(mode="json")
        md = render_md(js, cfg.get("rendering", {}))
        metrics = compute_metrics(state, briefing_obj, cfg)
        logger.info(
            "multi-stage summarize took_ms=%d metrics=%s",
            int((time.monotonic()-t2) * 1000),
            metrics,
        )
        if state.artifact_root:
            metrics_path = state.artifact_root / "metrics.json"
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    else:
        t2 = time.monotonic()
        md, js = generate_summary(bundles, cfg)
        logger.info("summarized took_ms=%d", int((time.monotonic()-t2)*1000))

    if md is None or js is None:
        logger.info("empty briefing -> skip output & publish")
        return

    out_dir = cfg["output"]["dir"]
    generated_files = write_output(md, js, cfg["output"])
    logger.info("output written dir=%s", out_dir)

    try:
        maybe_publish_telegram(md, cfg["output"])
    except Exception as e:
        logger.error("telegram publish failed: %s", e)

    try:
        maybe_briefing_archive(generated_files, cfg["output"], briefing_id, run_id)
    except Exception as e:
        logger.error("github backup failed: %s", e)

    logger.info("OK: briefing generated and published.")

def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="Run a briefing generation task.")
    parser.add_argument('--config', type=str, required=True, help="Path to the briefing config YAML file.")
    parser.add_argument('--multi-stage', dest='multi_stage', action='store_true', help="Enable multi-stage LLM pipeline")
    parser.add_argument('--single-stage', dest='multi_stage', action='store_false', help="Use legacy single-stage summarizer")
    parser.add_argument('--agentic-section', dest='agentic_section', action='store_true', help="Force Agentic Focus section")
    parser.add_argument('--no-agentic-section', dest='agentic_section', action='store_false', help="Disable Agentic Focus section")
    parser.add_argument('--brief-lite', dest='brief_lite', action='store_true', help="Emit condensed brief if available")
    parser.add_argument('--no-brief-lite', dest='brief_lite', action='store_false', help="Skip condensed brief")
    parser.set_defaults(multi_stage=None, agentic_section=None, brief_lite=None)
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:8]
    logger.info("=== run start id=%s ===", run_id)

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        validate_config(cfg)
        overrides = {
            "multi_stage": args.multi_stage,
            "agentic_section": args.agentic_section,
            "brief_lite": args.brief_lite,
        }
        _execute_pipeline(cfg, run_id, overrides)
        
    except Exception as e:
        logger.error("Pipeline execution failed: %s", e)
        raise
    finally:
        logger.info("=== run end id=%s ===", run_id)

if __name__ == "__main__":
    main()



def run_once(
    config_path: str,
    *,
    multi_stage: Optional[bool] = None,
    agentic_section: Optional[bool] = None,
    brief_lite: Optional[bool] = None,
) -> None:
    """Execute pipeline once with given config file path."""
    run_id = uuid.uuid4().hex[:8]
    logger.info("=== run start id=%s ===", run_id)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        validate_config(cfg)
        overrides = {
            "multi_stage": multi_stage,
            "agentic_section": agentic_section,
            "brief_lite": brief_lite,
        }
        _execute_pipeline(cfg, run_id, overrides)
        
    except Exception as e:
        logger.error("Pipeline execution failed: %s", e)
        raise
    finally:
        logger.info("=== run end id=%s ===", run_id)
