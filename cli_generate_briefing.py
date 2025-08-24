#!/usr/bin/env python3
import argparse, json, os
from utils import get_logger, load_file, write_output, validate_config
from orchestrator import _fetch_items, _process_items
from summarizer import generate_summary

logger = get_logger(__name__)

def main():
    ap = argparse.ArgumentParser(description="Generate AI briefing from a config YAML")
    ap.add_argument("--config", required=True, help="Path to YAML config file")
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(load_file(args.config))
    validate_config(cfg)

    items = _fetch_items(cfg["source"])
    bundles = _process_items(items, cfg["processing"])

    md, js = generate_summary(bundles, cfg)
    if md and js:
        write_output(md, js, cfg["output"])
        print("OK: briefing generated.")
    else:
        print("No content, skipped.")

if __name__ == "__main__":
    main()
