"""
HTTP utilities for making requests with retry logic and error handling.

This module provides functions for making HTTP requests with proper retry logic,
error handling, and logging.
"""

import asyncio
from typing import Dict, Any, Optional, Union, Tuple
import random
import time
from urllib.parse import urlencode, quote_plus

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from loguru import logger

from src.config import (
    HEADERS,
    REQUEST_TIMEOUT,
    RETRY_CONFIG,
    get_random_delay,
)


def build_search_url(search_term: str, page: int = 1) -> str:
    """
    Build a search URL for Prom.ua.

    Args:
        search_term: The search query
        page: Page number (default: 1)

    Returns:
        Properly formatted search URL
    """
    # Encode the search term for URL
    encoded_term = quote_plus(search_term)

    # Build the URL with the encoded search term and page number
    return f"https://prom.ua/ua/search?search_term={encoded_term}&page={page}"


def is_empty_response(response: httpx.Response) -> bool:
    """
    Check if the response contains no useful data.

    Args:
        response: The HTTP response to check

    Returns:
        True if the response is empty or contains error page
    """
    # Check if response is empty
    if not response.text:
        return True

    # Check for common error indicators
    error_indicators = [
        "<title>access denied</title>",
        "<title>error</title>",
        "captcha",
        "robot detection",
    ]

    # Convert response text to lowercase for case-insensitive matching
    response_text_lower = response.text.lower()

    for indicator in error_indicators:
        if indicator in response_text_lower:
            return True

    return False


@retry(
    stop=stop_after_attempt(RETRY_CONFIG["max_attempts"]),
    wait=wait_random_exponential(
        multiplier=1,
        min=RETRY_CONFIG["min_delay"],
        max=RETRY_CONFIG["max_delay"],
    ),
    retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
    before_sleep=before_sleep_log(logger, "INFO"),
)
async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    session_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """
    Fetch a URL with retry logic.

    Args:
        client: The HTTPX client to use
        url: The URL to fetch
        session_id: Optional session ID for logging
        headers: Optional headers to use (defaults to config.HEADERS)

    Returns:
        The HTTP response

    Raises:
        httpx.HTTPError: If the request fails after all retries
    """
    # Use default headers if none provided
    request_headers = headers or HEADERS.copy()

    # Add a session identifier to the log
    session_info = f" [Session: {session_id}]" if session_id else ""

    # Log the request
    logger.info(f"Fetching URL: {url}{session_info}")

    # Add a random delay before the request
    await asyncio.sleep(get_random_delay())

    # Make the request
    start_time = time.time()
    response = await client.get(
        url,
        headers=request_headers,
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )
    elapsed = time.time() - start_time

    # Log the response
    logger.info(
        f"Response: {response.status_code} | {len(response.content)} bytes | "
        f"{elapsed:.2f}s{session_info} | {url}"
    )

    # Check for error status codes
    response.raise_for_status()

    # Check if response is empty or contains error page
    if is_empty_response(response):
        logger.warning(
            f"Response contains error indicators{session_info}."
        )
        # Don't raise an error, just log a warning
        # We'll handle empty pages in the crawler code

    return response


async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
    session_id: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    """
    Fetch HTML content from a URL.

    Args:
        client: The HTTPX client to use
        url: The URL to fetch
        session_id: Optional session ID for logging
        headers: Optional headers to use

    Returns:
        The HTML content as a string
    """
    response = await fetch_with_retry(client, url, session_id, headers)
    return response.text
