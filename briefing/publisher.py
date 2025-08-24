
import os
import subprocess
import requests
from typing import Optional

from briefing.utils import get_logger, redact_secrets

logger = get_logger(__name__)

# ---------- Telegram ----------

def telegram_send(text: str, chat_id: str, bot_token: str, parse_mode: Optional[str] = None, chunk_size: int = 3500):
    base = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)] or [text]
    sent = 0
    for ck in chunks:
        payload = {"chat_id": chat_id, "text": ck}
        if parse_mode and parse_mode != "None":
            payload["parse_mode"] = parse_mode
        r = requests.post(base, json=payload, timeout=30)
        if r.status_code != 200:
            logger.error("telegram_send failed status=%s body=%s", r.status_code, redact_secrets(r.text))
            raise RuntimeError(f"Telegram send failed: {r.text}")
        sent += 1
    logger.info("telegram_send success parts=%d", sent)

def maybe_publish_telegram(markdown_text: str, output_cfg: dict):
    tg = (output_cfg or {}).get("telegram") or {}
    if not tg.get("enabled"):
        return
    chat_id = tg.get("chat_id")
    parse_mode = tg.get("parse_mode", "None")
    chunk_size = int(tg.get("chunk_size", 3500))
    token_env = tg.get("bot_token_env", "TELEGRAM_BOT_TOKEN")
    bot_token = os.getenv(token_env, "")
    if not (chat_id and bot_token):
        logger.warning("telegram not configured: chat_id or token missing")
        return
    telegram_send(markdown_text, chat_id, bot_token, parse_mode=parse_mode, chunk_size=chunk_size)

# ---------- GitHub backup ----------

def _run_safe(cmd_args, cwd=None, env=None):
    """Execute git commands safely with whitelist validation."""
    # Whitelist of allowed git commands
    ALLOWED_GIT_COMMANDS = [
        'init', 'config', 'remote', 'add', 'set-url', 
        'checkout', 'add', 'commit', 'push', 'status', 
        'rev-parse', 'log', 'diff'
    ]
    
    # Validate command
    if not cmd_args or len(cmd_args) < 2:
        raise ValueError("Invalid command format")
    
    if cmd_args[0] != 'git':
        raise ValueError(f"Only git commands are allowed, got: {cmd_args[0]}")
    
    if cmd_args[1] not in ALLOWED_GIT_COMMANDS:
        raise ValueError(f"Git subcommand '{cmd_args[1]}' not allowed")
    
    # Redact sensitive information for logging
    safe_cmd = [c if "x-access-token" not in c else "***" for c in cmd_args]
    logger.info("git$ %s", " ".join(safe_cmd))
    
    # Execute with shell=False for safety
    cp = subprocess.run(cmd_args, shell=False, cwd=cwd, env=env, capture_output=True, text=True)
    if cp.returncode != 0:
        logger.error("git failed: rc=%d stdout=%s stderr=%s", cp.returncode, 
                    redact_secrets(cp.stdout), redact_secrets(cp.stderr))
        raise RuntimeError(f"git error: {redact_secrets(cp.stderr)}")
    return cp.stdout.strip()

def _tokenized_url(url: str, token: str) -> str:
    if not url or not url.startswith("https://") or not token:
        return url
    return url.replace("https://", f"https://x-access-token:{token}@")

def maybe_github_backup(output_dir: str, output_cfg: dict, briefing_id: str, run_id: str):
    gb = (output_cfg or {}).get("github_backup") or {}
    if not gb.get("enabled"):
        return

    repo_dir = gb.get("repo_dir", ".")
    branch = gb.get("branch", "main")
    author_name = os.getenv(gb.get("author_name_env", "GIT_AUTHOR_NAME"), "AI Briefing Bot")
    author_email = os.getenv(gb.get("author_email_env", "GIT_AUTHOR_EMAIL"), "bot@example.com")
    token = os.getenv(gb.get("token_env", "GITHUB_TOKEN"), "")
    repo_url_cfg = gb.get("repo_url", "")
    pathspec = gb.get("pathspec") or output_dir
    commit_prefix = gb.get("commit_message_prefix", "briefing")

    try:
        _run_safe(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
        logger.info("github_backup: using existing git repo at %s", repo_dir)
    except Exception:
        logger.info("github_backup: init new repo at %s", repo_dir)
        _run_safe(["git", "init"], cwd=repo_dir)

    if repo_url_cfg:
        try:
            _run_safe(["git", "remote", "add", "origin", _tokenized_url(repo_url_cfg, token)], cwd=repo_dir)
        except Exception:
            _run_safe(["git", "remote", "set-url", "origin", _tokenized_url(repo_url_cfg, token)], cwd=repo_dir)

    _run_safe(["git", "config", "user.name", author_name], cwd=repo_dir)
    _run_safe(["git", "config", "user.email", author_email], cwd=repo_dir)
    _run_safe(["git", "checkout", "-B", branch], cwd=repo_dir)
    _run_safe(["git", "add", "--all", pathspec], cwd=repo_dir)

    status = _run_safe(["git", "status", "--porcelain"], cwd=repo_dir)
    if not status:
        logger.info("github_backup: no changes detected for pathspec=%s", pathspec)
        return

    msg = f"{commit_prefix}: {briefing_id} run={run_id}"
    _run_safe(["git", "commit", "-m", msg], cwd=repo_dir)

    try:
        _run_safe(["git", "push", "origin", branch], cwd=repo_dir)
    except Exception as e:
        logger.error("github_backup push failed: %s", e)
        raise
    logger.info("github_backup: pushed branch=%s pathspec=%s", branch, pathspec)

