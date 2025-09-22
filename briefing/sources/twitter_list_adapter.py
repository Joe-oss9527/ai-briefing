
import os
import requests
from typing import List, Dict, Any

from briefing.utils import clean_text, parse_datetime_safe, get_logger

RSSHUB_ORIGIN = os.getenv("RSSHUB_ORIGIN", "http://rsshub:1200")
logger = get_logger(__name__)

def fetch(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    list_id = source_config["id"]
    url = f"{RSSHUB_ORIGIN}/twitter/list/{list_id}?format=json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = []

    for entry in data.get("items", []):
        raw_text = entry.get("description") or entry.get("title") or ""
        text = clean_text(raw_text)
        if not text:
            continue

        raw_ts = (
            entry.get("date_published")
            or entry.get("dateModified")
            or entry.get("date_modified")
            or entry.get("pubDate")
            or entry.get("date")
            or ""
        )

        timestamp = None
        if raw_ts:
            timestamp = parse_datetime_safe(raw_ts)

        if timestamp is None:
            logger.warning("twitter_list_adapter: drop item %s due to missing/invalid timestamp", entry.get("id"))
            continue

        author = "Unknown"
        if isinstance(entry.get("author"), dict):
            author = entry["author"].get("name", author)
        elif isinstance(entry.get("author"), str):
            author = entry["author"]

        items.append({
            "id": entry.get("id") or entry.get("url"),
            "text": text,
            "url": entry.get("url", ""),
            "author": author,
            "timestamp": timestamp.isoformat(),
            "metadata": {"source": "twitter"}
        })

    logger.info("twitter_list_adapter fetched_items=%d", len(items))
    return items
