
import feedparser
from typing import List, Dict, Any
from briefing.utils import clean_text, parse_datetime_safe, get_logger

logger = get_logger(__name__)

def fetch(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    urls = source_config.get("urls", [])
    items: List[Dict[str, Any]] = []

    for url in urls:
        feed = feedparser.parse(url)
        for e in feed.entries:
            raw = e.get("summary") or e.get("title") or ""
            text = clean_text(raw)
            if not text:
                continue

            ts = parse_datetime_safe(
                e.get("published") or e.get("updated") or ""
            )

            items.append({
                "id": e.get("id") or e.get("link") or e.get("title"),
                "text": text,
                "url": e.get("link") or "",
                "author": getattr(e, "author", "Unknown"),
                "timestamp": ts.isoformat(),
                "metadata": {"source": "rss"}
            })

    logger.info("rss_adapter fetched_items=%d", len(items))
    return items

