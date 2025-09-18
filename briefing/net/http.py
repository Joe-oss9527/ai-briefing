"""HTTP helpers providing resilient sessions with retries."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def retry_session(
    total: int = 3,
    backoff: float = 0.5,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    allowed_methods: frozenset[str] | None = None,
) -> requests.Session:
    """Create a requests session with retry configuration.

    Follows guidance from urllib3's Retry docs and Telegram/GitHub API rate-limit
    recommendations by retrying on transient 429/5xx responses.
    """

    methods = allowed_methods or frozenset({"GET", "POST", "PUT"})
    session = requests.Session()
    retry = Retry(
        total=total,
        read=total,
        connect=total,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=methods,
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
