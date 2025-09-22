
import os
import time
import json
import math
import datetime as dt
import numpy as np
import requests
import fasttext
from typing import List, Dict, Any, Tuple
from sklearn.metrics.pairwise import cosine_similarity
import hdbscan
from sentence_transformers import CrossEncoder

from briefing.utils import now_utc, get_logger, parse_datetime_safe

TEI_ORIGIN = os.getenv("TEI_ORIGIN", "http://tei:3000")
LID_MODEL_PATH = os.getenv("LID_MODEL_PATH", "/workspace/lid.176.bin")
logger = get_logger(__name__)

def _normalize_text_encoding(text: str) -> str:
    """Normalize text encoding to ensure valid UTF-8."""
    original_text = text
    
    # Ensure text is a string
    if not isinstance(text, str):
        logger.debug("Converting non-string input to string: %s", type(text).__name__)
        text = str(text)
    
    # Handle bytes input
    if isinstance(text, bytes):
        logger.debug("Converting bytes to UTF-8 string")
        text = text.decode('utf-8', errors='replace')
    
    # Ensure proper UTF-8 encoding
    text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    
    if text != original_text and isinstance(original_text, str):
        logger.debug("Text encoding normalized: %s characters changed", 
                    sum(1 for a, b in zip(original_text[:100], text[:100]) if a != b))
    
    return text

def _remove_invalid_escapes(text: str) -> str:
    """Remove incomplete hex/unicode escape sequences that cause JSON parsing errors."""
    import re
    
    original_text = text
    changes = 0
    
    # Replace incomplete \x sequences (not followed by exactly 2 hex digits)
    new_text = re.sub(r'\\x(?![0-9a-fA-F]{2})', ' ', text)
    if new_text != text:
        changes += len(re.findall(r'\\x(?![0-9a-fA-F]{2})', text))
        text = new_text
    
    # Replace incomplete \u sequences (not followed by exactly 4 hex digits) 
    new_text = re.sub(r'\\u(?![0-9a-fA-F]{4})', ' ', text)
    if new_text != text:
        changes += len(re.findall(r'\\u(?![0-9a-fA-F]{4})', text))
        text = new_text
    
    # Replace literal backslashes that might cause issues
    backslash_count = text.count('\\')
    text = text.replace('\\', ' ')
    if backslash_count > 0:
        changes += backslash_count
    
    if changes > 0:
        logger.debug("Removed %d invalid escape sequences from text", changes)
    
    return text

def _filter_control_chars(text: str) -> str:
    """Remove control characters except common whitespace."""
    # Keep only printable characters and common whitespace
    original_len = len(text)
    filtered_text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    removed_count = original_len - len(filtered_text)
    if removed_count > 0:
        logger.debug("Filtered %d control characters from text", removed_count)
    
    return filtered_text

def _clean_text_for_embedding(text: str) -> str:
    """Clean text to prevent JSON parsing errors in TEI service."""
    text = _normalize_text_encoding(text)
    text = _remove_invalid_escapes(text)
    text = _filter_control_chars(text)
    return text.strip()

def _embed_texts(texts: List[str]) -> np.ndarray:
    st = time.monotonic()
    batch_size = 16  # Process texts in smaller batches
    all_embs = []
    
    # Clean all texts before processing
    cleaned_texts = [_clean_text_for_embedding(text) for text in texts]
    cleaned_count = sum(1 for orig, clean in zip(texts, cleaned_texts) if orig != clean)
    if cleaned_count > 0:
        logger.info("Cleaned %d texts for embedding processing", cleaned_count)
    
    for i in range(0, len(cleaned_texts), batch_size):
        batch = cleaned_texts[i:i+batch_size]
        
        # Retry mechanism for TEI API calls
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(f"{TEI_ORIGIN}/embeddings", json={"input": batch}, timeout=60)
                resp.raise_for_status()
                break
            except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
                if attempt == max_retries - 1:
                    logger.error("TEI embedding failed after %d attempts: %s", max_retries, e)
                    raise
                logger.warning("TEI embedding attempt %d failed, retrying: %s", attempt + 1, e)
                time.sleep(2 ** attempt)  # Exponential backoff
        
        data = resp.json()
        if "data" in data:
            embs = [d["embedding"] for d in data["data"]]
        else:
            embs = data["embeddings"]
        all_embs.extend(embs)
    
    arr = np.array(all_embs, dtype=np.float32)
    logger.info("embed_texts count=%d took_ms=%d", len(texts), int((time.monotonic()-st)*1000))
    return arr

def _near_duplicate_mask(embs: np.ndarray, threshold: float) -> List[bool]:
    n = embs.shape[0]
    keep = [True] * n
    duplicates_found = 0
    sims = cosine_similarity(embs)
    
    for i in range(n):
        if not keep[i]:
            continue
        for j in range(i + 1, n):
            if keep[j] and sims[i, j] >= threshold:
                keep[j] = False
                duplicates_found += 1
                logger.debug("Duplicate detected: item %d similar to %d (similarity=%.3f)", j, i, sims[i, j])
    
    logger.info("Near-duplicate detection: %d duplicates found out of %d items (threshold=%.2f)", 
                duplicates_found, n, threshold)
    return keep

def _cluster(embs: np.ndarray, min_cluster_size: int) -> np.ndarray:
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric='euclidean')
    labels = clusterer.fit_predict(embs)
    
    unique_labels = set(labels)
    n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
    n_noise = list(labels).count(-1)
    
    logger.info("Clustering complete: %d clusters found, %d noise points (min_size=%d)", 
                n_clusters, n_noise, min_cluster_size)
    return labels

def _cluster_centrality(embs: np.ndarray, idxs: List[int]) -> Tuple[int, np.ndarray]:
    sub = embs[idxs]
    sims = cosine_similarity(sub, sub)
    scores = sims.mean(axis=1)
    best_local = int(np.argmax(scores))
    return idxs[best_local], sub[best_local]

def _top_k_by_centroid(embs: np.ndarray, idxs: List[int], k: int = 50) -> List[int]:
    centroid = embs[idxs].mean(axis=0, keepdims=True)
    sims = cosine_similarity(embs[idxs], centroid).reshape(-1)
    order = np.argsort(-sims)
    pick = [idxs[i] for i in order[: min(k, len(idxs))]]
    return pick

def _rerank(bge_model: str, query: str, candidates: List[str]) -> List[int]:
    st = time.monotonic()
    ce = CrossEncoder(bge_model)
    # Ensure all candidates are clean strings
    clean_candidates = [_clean_text_for_embedding(c) for c in candidates]
    pairs = [[_clean_text_for_embedding(query), c] for c in clean_candidates]
    scores = ce.predict(pairs)
    order = np.argsort(-scores)
    logger.info("rerank candidates=%d took_ms=%d", len(candidates), int((time.monotonic()-st)*1000))
    return order.tolist()

def run_processing_pipeline(raw_items: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not raw_items:
        return []

    horizon = now_utc().timestamp() - cfg["time_window_hours"] * 3600
    filtered = []
    items_too_old = 0
    items_invalid_ts = 0
    
    for it in raw_items:
        try:
            ts = it["timestamp"]
            if isinstance(ts, str):
                parsed_dt = parse_datetime_safe(ts)
                if parsed_dt is None:
                    raise ValueError("invalid timestamp string")
                t = parsed_dt.timestamp()
            elif isinstance(ts, dt.datetime):
                parsed_dt = ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
                t = parsed_dt.timestamp()
            elif isinstance(ts, (int, float)):
                t = float(ts)
            else:
                raise TypeError(f"unsupported timestamp type: {type(ts)}")
        except Exception as e:
            logger.warning("Failed to parse timestamp for item %s: %s", it.get("id"), str(e))
            items_invalid_ts += 1
            continue
        
        if t >= horizon:
            filtered.append(it)
        else:
            items_too_old += 1
            logger.debug("Item %s filtered: too old (age=%.1f hours)", 
                        it.get("id"), (now_utc().timestamp() - t) / 3600)
    
    logger.info(
        "Time filter: kept %d items, filtered %d old items, dropped %d invalid timestamps (window=%d hours)",
        len(filtered), items_too_old, items_invalid_ts, cfg["time_window_hours"]
    )

    if not filtered:
        logger.info("pipeline: no items after time_window filter")
        return []

    # lid = fasttext.load_model(LID_MODEL_PATH)
    texts = [it["text"] for it in filtered]
    # for tx in texts:
    #     lid.predict(tx.replace("\n", " ")[:1000])  # 标注语言（当前未做强过滤）

    embs = _embed_texts(texts)

    mask = _near_duplicate_mask(embs, cfg.get("sim_near_dup", 0.92))
    filtered2 = [x for x, m in zip(filtered, mask) if m]
    embs2 = embs[mask]

    if len(filtered2) == 0:
        logger.info("pipeline: all items removed by near-dup filter")
        return []

    labels = _cluster(embs2, cfg.get("min_cluster_size", 3))
    clusters: Dict[int, List[int]] = {}
    for i, lb in enumerate(labels):
        clusters.setdefault(lb, []).append(i)

    bundles: List[Dict[str, Any]] = []
    initial_topk = int(cfg.get("initial_topk", 1000))
    max_candidates = int(cfg.get("max_candidates_per_cluster", 300))
    bge_model = cfg["reranker_model"]

    for lb, idxs in clusters.items():
        pick = _top_k_by_centroid(embs2, idxs, k=min(initial_topk, len(idxs)))
        pick = pick[:max_candidates]
        best_idx, _ = _cluster_centrality(embs2, idxs)
        query_text = filtered2[best_idx]["text"]
        cand_texts = [filtered2[i]["text"] for i in pick]
        order = _rerank(bge_model, query_text, cand_texts)
        ordered_items = [filtered2[pick[i]] for i in order]

        bundles.append({
            "topic_id": f"cluster-{lb}",
            "topic_label": None,
            "items": ordered_items
        })

    bundles.sort(key=lambda b: len(b["items"]), reverse=True)
    logger.info("pipeline: bundles=%d", len(bundles))
    return bundles
