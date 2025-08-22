import os
import re
import json
import html2text
import requests
import datetime as dt
import logging
from logging.handlers import TimedRotatingFileHandler
from jsonschema import validate, Draft202012Validator
from jsonschema.exceptions import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ---------- Time helpers ----------

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def parse_datetime_safe(raw: str) -> dt.datetime:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except Exception:
            continue
    return now_utc()

# ---------- Text helpers ----------

def clean_text(html_or_text: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    text = h.handle(html_or_text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ---------- Config validation ----------

def load_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def validate_config(cfg: dict):
    schema = json.loads(load_file("schemas/config.schema.json"))
    try:
        validate(instance=cfg, schema=schema, cls=Draft202012Validator)
    except ValidationError as e:
        raise ValueError(f"Config validation error: {e.message} at {list(e.path)}") from e

# ---------- Output writer ----------

def write_output(human_md: str, json_obj: dict, out_cfg: dict):
    out_dir = out_cfg["dir"]
    formats = out_cfg["formats"]
    os.makedirs(out_dir, exist_ok=True)
    ts = now_utc().strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(out_dir, f"briefing_{ts}")

    if "md" in formats:
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(human_md)

    if "json" in formats:
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=2)

    if "html" in formats:
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{json_obj.get('title','Briefing')}</title></head>
<body><pre>
{human_md}
</pre></body></html>"""
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(html)

# ---------- Logging ----------

_LOGGER_INITIALIZED = False

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": dt.datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def _build_logger():
    global _LOGGER_INITIALIZED
    if _LOGGER_INITIALIZED:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", "/workspace/logs")
    json_mode = os.getenv("LOG_JSON", "false").lower() == "true"

    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level, logging.INFO))

    ch = logging.StreamHandler()
    ch.setLevel(logger.level)

    fh = TimedRotatingFileHandler(os.path.join(log_dir, "ai-briefing.log"), when="D", backupCount=7, encoding="utf-8")
    fh.setLevel(logger.level)

    if json_mode:
        fmt = JsonFormatter()
    else:
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    ch.setFormatter(fmt)
    fh.setFormatter(fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)

    _LOGGER_INITIALIZED = True

def get_logger(name: str = None) -> logging.Logger:
    _build_logger()
    return logging.getLogger(name if name else __name__)

# ---------- Secret redaction ----------

def redact_secrets(s: str) -> str:
    """Redact sensitive information from strings for safe logging."""
    if not s:
        return s
    
    # Simple approach: redact known env vars
    env_keys = ["GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN", 
                "REDDIT_CLIENT_SECRET", "TWITTER_PASSWORD"]
    
    redacted = s
    for k in env_keys:
        v = os.getenv(k)
        if v and len(v) > 3:
            redacted = redacted.replace(v, "***")
    
    # Simple regex patterns for common cases
    import re
    redacted = re.sub(r"x-access-token:[^@]+@", "x-access-token:***@", redacted)
    redacted = re.sub(r"ghp_[A-Za-z0-9]{36}", "ghp_***", redacted)
    
    return redacted

# ---------- Service health wait ----------

@retry(stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception_type((requests.RequestException, AssertionError)))
def wait_for_service(url: str, expect_status: int = 200, timeout: float = 5.0):
    r = requests.get(url, timeout=timeout)
    assert r.status_code == expect_status
    return True