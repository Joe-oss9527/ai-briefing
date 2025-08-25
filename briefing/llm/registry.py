
"""LLM registry with native structured output support."""

import os
import json
import time
from .schema_adapter import to_gemini, to_openai

def call_openai(prompt: str, model: str, temperature: float, 
                timeout: int, retries: int, schema: dict, 
                options: dict = None) -> dict:
    """Call OpenAI with structured outputs."""
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")
    
    options = options or {}
    base_url = options.get("base_url")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema.get("title", "Response"),
            "strict": True,
            "schema": to_openai(schema)
        }
    }
    
    for attempt in range(retries + 1):
        try:
            resp = client.with_options(timeout=timeout).responses.create(
                model=model,
                input=prompt,
                text={"format": response_format},
                temperature=temperature
            )
            return json.loads(resp.output_text)
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(0.5 * (2 ** attempt))

def call_gemini(prompt: str, model: str, temperature: float,
                timeout: int, retries: int, schema: dict,
                options: dict = None) -> dict:
    """Call Gemini with structured outputs."""
    from google import genai
    
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required")
    
    client = genai.Client(api_key=api_key)
    config = {
        "response_mime_type": "application/json",
        "response_schema": to_gemini(schema),
        "temperature": temperature
    }
    
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            return json.loads(resp.text)
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(0.5 * (2 ** attempt))

def call_with_schema(provider: str, prompt: str, model: str, schema: dict,
                    temperature: float = 0.2, timeout: int = 600, 
                    retries: int = 0, options: dict = None) -> dict:
    """Unified structured output interface."""
    provider = provider.lower()
    
    if provider == "openai":
        return call_openai(prompt, model, temperature, timeout, retries, schema, options)
    elif provider == "gemini":
        return call_gemini(prompt, model, temperature, timeout, retries, schema, options)
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Keep legacy interface for backward compatibility with non-structured calls
def call_with_options(provider: str, prompt: str, model: str, temperature: float = 0.2, timeout: int = 600, retries: int = 0, options: dict = None) -> str:
    """Legacy interface - use call_with_schema for structured outputs."""
    raise NotImplementedError("Use call_with_schema for structured outputs")

