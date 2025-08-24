# ai_briefing/llm_adapters.py
"""
Strict adapters with configurable options and retries.

Supported provider_options:
- openai:
    base_url: str (optional)
    http_proxy / https_proxy: str (optional, e.g. http://127.0.0.1:7890)
- gemini:
    use_vertex: bool
    project: str
    location: str (default: us-central1)
    api_version: str (e.g., "v1")
- ollama:
    host: str (default: http://127.0.0.1:11434)

Common controls (read by caller):
- temperature: float
- timeout: int seconds
- retries: int (>=0), exponential backoff (0.5 * 2^attempt) seconds
"""

from __future__ import annotations
import os, time, contextlib
import requests


@contextlib.contextmanager
def _proxy_env(http_proxy: str | None, https_proxy: str | None):
    old_http = os.environ.get("HTTP_PROXY")
    old_https = os.environ.get("HTTPS_PROXY")
    try:
        if http_proxy:
            os.environ["HTTP_PROXY"] = http_proxy
        if https_proxy:
            os.environ["HTTPS_PROXY"] = https_proxy
        yield
    finally:
        if old_http is None:
            os.environ.pop("HTTP_PROXY", None)
        else:
            os.environ["HTTP_PROXY"] = old_http
        if old_https is None:
            os.environ.pop("HTTPS_PROXY", None)
        else:
            os.environ["HTTPS_PROXY"] = old_https


def call_openai(prompt: str, model: str, temperature: float, timeout: int, retries: int, options: dict | None = None) -> str:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI provider")
    options = options or {}
    base_url = options.get("base_url") or os.getenv("OPENAI_BASE_URL")
    http_proxy = options.get("http_proxy")
    https_proxy = options.get("https_proxy")

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    attempt = 0
    while True:
        try:
            with _proxy_env(http_proxy, https_proxy):
                resp = client.with_options(timeout=timeout).responses.create(
                    model=model,
                    input=prompt,
                    temperature=temperature,
                )
            return (getattr(resp, "output_text", None) or "").strip()
        except Exception as e:
            if attempt >= retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
            attempt += 1


def call_gemini(prompt: str, model: str, temperature: float, timeout: int, retries: int, options: dict | None = None) -> str:
    from google import genai
    from google.genai import types as genai_types
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key and not (options or {}).get("use_vertex"):
        raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) is required for Gemini Developer API")

    options = options or {}
    use_vertex = bool(options.get("use_vertex", False))
    project = options.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = options.get("location") or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    api_version = options.get("api_version")
    http_options = genai_types.HttpOptions(api_version=api_version) if api_version else None

    if use_vertex:
        if not project:
            raise RuntimeError("Gemini Vertex mode requires GCP project (set provider_options.project or GOOGLE_CLOUD_PROJECT)")
        client = genai.Client(vertexai=True, project=project, location=location, http_options=http_options)
    else:
        client = genai.Client(api_key=api_key, http_options=http_options)

    attempt = 0
    while True:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                generation_config={"temperature": temperature},
            )
            return (getattr(resp, "text", None) or "").strip()
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
            attempt += 1


def call_ollama(prompt: str, model: str, temperature: float, timeout: int, retries: int, options: dict | None = None) -> str:
    options = options or {}
    host = options.get("host") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
    url = f"{host.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }

    attempt = 0
    while True:
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            js = r.json()
            return (js.get("response") or (js.get("message") or {}).get("content") or "").strip()
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
            attempt += 1


def call_with_options(provider: str, prompt: str, model: str, temperature: float = 0.2, timeout: int = 600, retries: int = 0, options: dict | None = None) -> str:
    provider = (provider or "").lower()
    if provider == "openai":
        return call_openai(prompt, model, temperature, timeout, retries, options)
    if provider == "gemini":
        return call_gemini(prompt, model, temperature, timeout, retries, options)
    if provider == "ollama":
        return call_ollama(prompt, model, temperature, timeout, retries, options)
    raise ValueError(f"Unknown llm_provider={provider}")
