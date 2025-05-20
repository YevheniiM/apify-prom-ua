"""
Configuration settings for the Prom.ua crawler.

This module contains all configurable parameters for the crawler,
including HTTP headers, proxy settings, retry logic, and delays.
"""

from typing import Dict, Any, List, Optional
import random

# Base URL for Prom.ua search
BASE_URL = "https://prom.ua/ua/search"

# HTTP request headers to mimic a real browser
HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

# User agent rotation list for session pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
]

# Proxy configuration for Apify
PROXY_CONFIG = {
    "useApifyProxy": False,  # Set to False to run without Apify proxy
    "apifyProxyGroups": ["RESIDENTIAL"],
}

# HTTP request timeout in seconds
REQUEST_TIMEOUT = 30.0

# Retry configuration
RETRY_CONFIG = {
    "max_attempts": 5,
    "min_delay": 1.0,
    "max_delay": 10.0,
    "retry_on_status_codes": [429, 403, 500, 502, 503, 504],
}

# Delay between requests (in seconds)
MIN_REQUEST_DELAY = 0.2
MAX_REQUEST_DELAY = 0.6

def get_random_delay() -> float:
    """Generate a random delay between requests."""
    return random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)

# Session pool configuration
SESSION_POOL_CONFIG = {
    "max_sessions": 10,
    "session_options": {
        "max_usage_count": 100,
    },
}

# Regular expressions for parsing
PRODUCT_URL_REGEX = r'href="(/ua/p\d+-[^"\']+\.html)"'
JSONLD_REGEX = r'<script[^>]+type="application/ld\+json"[^>]*>(\{.*?"@type"\s*:\s*"Product".*?})</script>'

# Maximum number of pages to crawl (safety limit)
MAX_PAGES = 100

# Maximum length of HTML snippet to log on error
MAX_HTML_LOG_LENGTH = 400
