"""
Tests for HTTP utilities.
"""

import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

from src.utils.http import (
    build_search_url,
    is_empty_response,
    fetch_with_retry,
    fetch_html,
)


def test_build_search_url_simple():
    """Test building a search URL with a simple search term."""
    url = build_search_url("laptop", 1)
    assert url == "https://prom.ua/ua/search?search_term=laptop&page=1"


def test_build_search_url_with_spaces():
    """Test building a search URL with spaces in the search term."""
    url = build_search_url("gaming laptop", 1)
    assert url == "https://prom.ua/ua/search?search_term=gaming+laptop&page=1"


def test_build_search_url_with_special_chars():
    """Test building a search URL with special characters in the search term."""
    url = build_search_url("laptop 15.6\"", 1)
    assert "https://prom.ua/ua/search?search_term=laptop+15.6%22&page=1" == url


def test_build_search_url_with_cyrillic():
    """Test building a search URL with Cyrillic characters in the search term."""
    url = build_search_url("ноутбук", 1)
    assert "https://prom.ua/ua/search?search_term=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&page=1" == url


def test_build_search_url_different_page():
    """Test building a search URL with a different page number."""
    url = build_search_url("laptop", 5)
    assert url == "https://prom.ua/ua/search?search_term=laptop&page=5"


def test_build_search_url_empty_term():
    """Test building a search URL with an empty search term."""
    url = build_search_url("", 1)
    assert url == "https://prom.ua/ua/search?search_term=&page=1"


def test_is_empty_response_empty_text():
    """Test is_empty_response with empty text."""
    response = MagicMock()
    response.text = ""
    assert is_empty_response(response) is True


def test_is_empty_response_access_denied():
    """Test is_empty_response with access denied text."""
    # Create a real httpx.Response object instead of a MagicMock
    response = httpx.Response(
        200,
        content="<html><title>Access denied</title></html>".encode()
    )
    assert is_empty_response(response) is True


def test_is_empty_response_error():
    """Test is_empty_response with error text."""
    # Create a real httpx.Response object instead of a MagicMock
    response = httpx.Response(
        200,
        content="<html><title>Error</title></html>".encode()
    )
    assert is_empty_response(response) is True


def test_is_empty_response_captcha():
    """Test is_empty_response with captcha text."""
    response = MagicMock()
    response.text = "<html>Please solve this captcha</html>"
    assert is_empty_response(response) is True


def test_is_empty_response_valid():
    """Test is_empty_response with valid text."""
    response = MagicMock()
    response.text = "<html><title>Valid Page</title></html>"
    assert is_empty_response(response) is False


@pytest.mark.asyncio
async def test_fetch_with_retry_success():
    """Test fetch_with_retry with successful response."""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"test content"
    response.text = "test content"
    client.get.return_value = response

    with patch("asyncio.sleep", AsyncMock()):
        result = await fetch_with_retry(client, "https://example.com")
        assert result == response
        client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_html_success():
    """Test fetch_html with successful response."""
    client = AsyncMock()
    response = MagicMock()
    response.text = "test html"

    with patch("src.utils.http.fetch_with_retry", AsyncMock(return_value=response)):
        result = await fetch_html(client, "https://example.com")
        assert result == "test html"
