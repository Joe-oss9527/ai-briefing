
import feedparser
from typing import List, Dict, Any, Optional
from briefing.utils import clean_text, parse_datetime_safe, get_logger, normalize_http_url

logger = get_logger(__name__)

def _extract_entry_url(e: Any) -> Optional[str]:
    # Try standard link
    link = None
    try:
        link = e.get("link")
    except Exception:
        link = getattr(e, "link", None)
    candidates: list[str] = []
    if link:
        candidates.append(link)

    # Try links list with rel=alternate
    links = None
    try:
        links = e.get("links")
    except Exception:
        links = getattr(e, "links", None)
    if isinstance(links, list):
        alt = None
        for li in links:
            if isinstance(li, dict) and li.get("rel") == "alternate" and li.get("href"):
                alt = li["href"]
                break
        if alt:
            candidates.append(alt)
        else:
            for li in links:
                href = li.get("href") if isinstance(li, dict) else None
                if href:
                    candidates.append(href)
                    break

    # Try common original link fields
    for k in ("feedburner_origlink", "origlink", "originallink"):
        try:
            v = e.get(k)
        except Exception:
            v = getattr(e, k, None)
        if v:
            candidates.append(v)

    # As a last resort, if id looks like a URL, attempt it
    try:
        ident = e.get("id")
    except Exception:
        ident = getattr(e, "id", None)
    if ident:
        candidates.append(ident)

    for c in candidates:
        nu = normalize_http_url(c)
        if nu:
            return nu
    return None

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
                e.get("date_published")
                or e.get("dateModified")
                or e.get("date_modified")
                or e.get("published")
                or e.get("updated")
                or ""
            )

            if ts is None:
                logger.warning("rss_adapter: drop item %s due to missing/invalid timestamp", e.get("id") or e.get("link"))
                continue

            url_val = _extract_entry_url(e)
            if not url_val:
                logger.warning("rss_adapter: drop item %s due to missing/invalid link", e.get("id") or e.get("title"))
                continue

            items.append({
                "id": e.get("id") or e.get("link") or e.get("title"),
                "text": text,
                "url": url_val,
                "author": getattr(e, "author", "Unknown"),
                "timestamp": ts.isoformat(),
                "metadata": {"source": "rss"}
            })

    logger.info("rss_adapter fetched_items=%d", len(items))
    return items
