
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

def maybe_github_backup(generated_files: list, output_cfg: dict, briefing_id: str, run_id: str):
    gb = (output_cfg or {}).get("github_backup") or {}
    if not gb.get("enabled"):
        return

    token = os.getenv(gb.get("token_env", "GITHUB_TOKEN"), "")
    repo_path = gb.get("repo", "")
    branch = gb.get("branch", "main")
    commit_prefix = gb.get("commit_message_prefix", "briefing")

    if not token or not repo_path:
        logger.error("github_backup: missing token or repo")
        return

    success_count = 0
    from datetime import datetime
    import base64

    for file_path in generated_files:
        if not os.path.exists(file_path):
            continue

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Generate GitHub path with year/month organization
            now = datetime.now()
            filename = os.path.basename(file_path)
            github_path = f"{now.strftime('%Y')}/{now.strftime('%m')}/{briefing_id}/{filename}"

            # Upload via GitHub API
            if _upload_to_github(token, repo_path, github_path, content, 
                               f"{commit_prefix}: {briefing_id} {filename} run={run_id}"):
                success_count += 1
                logger.info("github_backup: uploaded %s", filename)
            else:
                logger.error("github_backup: failed to upload %s", filename)

        except Exception as e:
            logger.error("github_backup: error processing %s: %s", file_path, e)

    logger.info("github_backup: uploaded %d/%d files", success_count, len(generated_files))


def _upload_to_github(token: str, repo: str, file_path: str, content: str, commit_message: str) -> bool:
    """Upload file to GitHub via API"""
    import requests
    import base64

    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Check if file exists
    response = requests.get(api_url, headers=headers)
    existing_sha = None
    if response.status_code == 200:
        existing_sha = response.json().get('sha')

    # Prepare file content (GitHub API requires base64)
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    # Upload or update file
    data = {
        'message': commit_message,
        'content': content_b64
    }
    if existing_sha:
        data['sha'] = existing_sha

    response = requests.put(api_url, headers=headers, json=data)
    return response.status_code in [200, 201]

