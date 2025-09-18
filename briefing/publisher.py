"""Channel publishers for AI-Briefing outputs."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path
from typing import Iterable, Optional

import mistune

from briefing.net import retry_session
from briefing.utils import get_logger, redact_secrets

logger = get_logger(__name__)

ALLOWED_SCHEMES = ("http", "https", "mailto", "tg")
TELEGRAM_LIMIT = 4096


def _sanitize_url(url: str) -> str:
    if not url:
        return ""
    value = url.strip()
    if ":" in value:
        scheme = value.split(":", 1)[0].lower()
        if scheme not in ALLOWED_SCHEMES:
            return ""
    return value


class _TelegramHTMLRenderer(mistune.HTMLRenderer):
    def text(self, text: str) -> str:  # type: ignore[override]
        return html_escape(text)

    def emphasis(self, text: str) -> str:  # type: ignore[override]
        return f"<i>{text}</i>"

    def strong(self, text: str) -> str:  # type: ignore[override]
        return f"<b>{text}</b>"

    def link(self, text: str, url: str, title: Optional[str] = None) -> str:  # type: ignore[override]
        safe_url = _sanitize_url(url)
        if not safe_url:
            return text
        return f'<a href="{html_escape(safe_url, quote=True)}">{text or html_escape(safe_url)}</a>'

    def image(self, src: str, alt: str = "", title: Optional[str] = None) -> str:  # type: ignore[override]
        safe_url = _sanitize_url(src)
        if not safe_url:
            return ""
        label = alt or "image"
        return f'🖼️ <a href="{html_escape(safe_url, quote=True)}">{html_escape(label)}</a>'

    def codespan(self, text: str) -> str:  # type: ignore[override]
        return f"<code>{html_escape(text)}</code>"

    def paragraph(self, text: str) -> str:  # type: ignore[override]
        return text + "\n\n"

    def heading(self, text: str, level: int) -> str:  # type: ignore[override]
        return f"<b>{text}</b>\n\n"

    def list(self, text: str, ordered: bool, **attrs) -> str:  # type: ignore[override]
        start = int(attrs.get("start") or 1)
        items = [line for line in text.strip("\n").split("\n") if line]
        bullets = []
        for index, item in enumerate(items, start=start):
            bullet = f"{index}. " if ordered else "• "
            bullets.append(bullet + item.strip())
        return "\n".join(bullets) + "\n\n"

    def list_item(self, text: str) -> str:  # type: ignore[override]
        return text.strip() + "\n"

    def block_quote(self, text: str) -> str:  # type: ignore[override]
        return f"<blockquote>{text.strip()}</blockquote>\n\n"

    def block_code(self, code: str, info: Optional[str] = None) -> str:  # type: ignore[override]
        language = (info or "").split()[0] if info else ""
        escaped = html_escape(code)
        if language:
            return f'<pre><code class="language-{html_escape(language)}">{escaped}</code></pre>\n'
        return f"<pre>{escaped}</pre>\n"

    def thematic_break(self) -> str:  # type: ignore[override]
        return "────────\n"


def md_to_tg_html(markdown_text: str, limit: int = TELEGRAM_LIMIT, headroom: int = 100) -> str:
    normalized = (markdown_text or "").replace("\r\n", "\n").strip()
    parser = mistune.create_markdown(
        renderer=_TelegramHTMLRenderer(),
        plugins=["strikethrough", "task_lists"],
    )
    html = parser(normalized)
    html = re.sub(r"</?(?:p|ul|ol|li|hr|table|thead|tbody|tr|th|td|div)>", "", html, flags=re.IGNORECASE)
    html = html.replace("&nbsp;", " ")
    max_len = max(1, min(limit, TELEGRAM_LIMIT) - max(0, headroom))
    return html[:max_len].strip()


def split_html_for_telegram(html: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    text = html or ""
    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = max(
            text.rfind("\n\n", 0, limit),
            text.rfind("</pre>", 0, limit),
            text.rfind("</blockquote>", 0, limit),
        )
        if cut == -1 or cut < int(limit * 0.7):
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    return parts


@dataclass
class TelegramConfig:
    chat_id: str
    bot_token: str
    parse_mode: Optional[str] = "HTML"
    link_preview_disabled: bool = True
    chunk_limit: int = TELEGRAM_LIMIT
    timeout_sec: float = 30.0
    retries: int = 3


class TelegramPublisher:
    def __init__(self, cfg: TelegramConfig):
        self.cfg = cfg
        self.session = retry_session(total=cfg.retries)

    def send_markdown(self, markdown_text: str) -> None:
        if not (self.cfg.chat_id and self.cfg.bot_token):
            raise RuntimeError("telegram: chat_id or bot_token missing")

        text = markdown_text or ""
        if self.cfg.parse_mode == "HTML":
            text = md_to_tg_html(text)
        chunks = split_html_for_telegram(text, min(self.cfg.chunk_limit, TELEGRAM_LIMIT))
        url = f"https://api.telegram.org/bot{self.cfg.bot_token}/sendMessage"

        for chunk in chunks:
            payload = {"chat_id": self.cfg.chat_id, "text": chunk}
            if self.cfg.parse_mode and self.cfg.parse_mode != "None":
                payload["parse_mode"] = self.cfg.parse_mode
            payload["link_preview_options"] = {"is_disabled": self.cfg.link_preview_disabled}
            response = self.session.post(url, json=payload, timeout=self.cfg.timeout_sec)
            if response.status_code != 200:
                logger.error(
                    "telegram_send failed status=%s body=%s",
                    response.status_code,
                    redact_secrets(response.text),
                )
                raise RuntimeError(f"Telegram send failed: {response.text[:256]}")
        logger.info("telegram_send success parts=%d", len(chunks))


def maybe_publish_telegram(markdown_text: str, output_cfg: dict) -> None:
    tg = (output_cfg or {}).get("telegram") or {}
    if not tg.get("enabled"):
        return

    token = tg.get("bot_token") or os.getenv(tg.get("bot_token_env", "TELEGRAM_BOT_TOKEN"), "")
    cfg = TelegramConfig(
        chat_id=tg.get("chat_id", ""),
        bot_token=token,
        parse_mode=(tg.get("parse_mode") if "parse_mode" in tg else "HTML") or None,
        link_preview_disabled=bool(tg.get("disable_link_preview", True)),
        chunk_limit=int(tg.get("chunk_size", TELEGRAM_LIMIT)),
        timeout_sec=float(tg.get("timeout_sec", 30.0)),
        retries=int(tg.get("retries", 3)),
    )

    if not (cfg.chat_id and cfg.bot_token):
        logger.warning("telegram not configured: chat_id or token missing")
        return

    TelegramPublisher(cfg).send_markdown(markdown_text)


@dataclass
class GitHubArtifactStoreConfig:
    repo: str
    token: str
    branch: str = "main"
    commit_prefix: str = "briefing"
    committer_name: str = "ai-briefing"
    committer_email: str = "noreply@example.com"
    retries: int = 3
    timeout_sec: float = 30.0


class GitHubArtifactStore:
    def __init__(self, cfg: GitHubArtifactStoreConfig):
        self.cfg = cfg
        self.session = retry_session(total=cfg.retries)
        self.headers = {
            "Authorization": f"token {cfg.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _contents_api(self, path: str) -> str:
        target = path.lstrip("/")
        return f"https://api.github.com/repos/{self.cfg.repo}/contents/{target}"

    def upload(self, local_path: Path, dest_path: str, commit_message: str) -> None:
        if not (self.cfg.token and self.cfg.repo):
            raise RuntimeError("github: token or repo missing")

        url = self._contents_api(dest_path)
        params = {"ref": self.cfg.branch}
        response = self.session.get(url, headers=self.headers, params=params, timeout=self.cfg.timeout_sec)
        existing_sha = response.json().get("sha") if response.status_code == 200 else None

        data = local_path.read_bytes()
        encoded = __import__("base64").b64encode(data).decode("utf-8")
        payload = {
            "message": commit_message,
            "content": encoded,
            "branch": self.cfg.branch,
            "committer": {
                "name": self.cfg.committer_name,
                "email": self.cfg.committer_email,
            },
        }
        if existing_sha:
            payload["sha"] = existing_sha

        put = self.session.put(url, headers=self.headers, json=payload, timeout=self.cfg.timeout_sec)
        if put.status_code not in (200, 201):
            logger.error(
                "github upload failed status=%s body=%s",
                put.status_code,
                redact_secrets(put.text),
            )
            raise RuntimeError(f"github put failed: {put.status_code} {put.text[:256]}")


def maybe_github_backup(generated_files: Iterable[str], output_cfg: dict, briefing_id: str, run_id: str) -> None:
    gb = (output_cfg or {}).get("github_backup") or {}
    if not gb.get("enabled"):
        return

    token = gb.get("token") or os.getenv(gb.get("token_env", "GITHUB_TOKEN"), "")
    repo = gb.get("repo") or gb.get("repo_url", "")
    cfg = GitHubArtifactStoreConfig(
        repo=repo,
        token=token,
        branch=gb.get("branch", "main"),
        commit_prefix=gb.get("commit_message_prefix", "briefing"),
        committer_name=gb.get("committer_name", "ai-briefing"),
        committer_email=gb.get("committer_email", "noreply@example.com"),
        retries=int(gb.get("retries", 3)),
        timeout_sec=float(gb.get("timeout_sec", 30.0)),
    )

    if not (cfg.token and cfg.repo):
        logger.error("github_backup: missing token or repo")
        return

    store = GitHubArtifactStore(cfg)
    now = __import__("datetime").datetime.now()
    files = [Path(p) for p in (generated_files or [])]
    if not files:
        return

    success = 0
    for path in files:
        if not path.exists():
            logger.warning("github_backup: file not found %s", path)
            continue
        destination = f"{now:%Y}/{now:%m}/{briefing_id}/{path.name}"
        message = f"{cfg.commit_prefix}: {briefing_id} {path.name} run={run_id}"
        try:
            store.upload(path, destination, message)
        except Exception as exc:  # pragma: no cover - network errors are logged
            logger.error("github_backup: failed upload %s error=%s", path.name, exc)
        else:
            success += 1
            logger.info("github_backup: uploaded %s", path.name)

    logger.info("github_backup: uploaded %d/%d files", success, len(files))


def _run_safe(cmd_args, cwd=None, env=None):
    """Execute git commands safely with whitelist validation (legacy helper)."""
    allowed = [
        "init",
        "config",
        "remote",
        "add",
        "set-url",
        "checkout",
        "commit",
        "push",
        "status",
        "rev-parse",
        "log",
        "diff",
    ]

    if not cmd_args or len(cmd_args) < 2:
        raise ValueError("Invalid command format")
    if cmd_args[0] != "git":
        raise ValueError(f"Only git commands are allowed, got: {cmd_args[0]}")
    if cmd_args[1] not in allowed:
        raise ValueError(f"Git subcommand '{cmd_args[1]}' not allowed")

    safe_cmd = [part if "x-access-token" not in part else "***" for part in cmd_args]
    logger.info("git$ %s", " ".join(safe_cmd))

    completed = subprocess.run(
        cmd_args,
        shell=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        logger.error(
            "git failed: rc=%d stdout=%s stderr=%s",
            completed.returncode,
            redact_secrets(completed.stdout),
            redact_secrets(completed.stderr),
        )
        raise RuntimeError(f"git error: {redact_secrets(completed.stderr)}")
    return completed.stdout.strip()
