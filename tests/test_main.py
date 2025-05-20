"""
Tests for the main module.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.main import setup_http_client, process_search, main


@pytest.mark.asyncio
async def test_setup_http_client_no_proxy():
    """Test setup_http_client without proxy."""
    with patch("src.main.PROXY_CONFIG", {"useApifyProxy": False}):
        with patch("httpx.AsyncClient") as mock_client:
            client = await setup_http_client()
            mock_client.assert_called_once()
            # Check that proxy is not in the client params
            args, kwargs = mock_client.call_args
            assert "proxy" not in kwargs


@pytest.mark.asyncio
async def test_setup_http_client_with_proxy():
    """Test setup_http_client with proxy."""
    mock_proxy_config = MagicMock()
    mock_proxy_config.new_url = AsyncMock(return_value="http://proxy.example.com")

    with patch("src.main.PROXY_CONFIG", {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}):
        with patch("src.main.Actor.create_proxy_configuration", AsyncMock(return_value=mock_proxy_config)):
            with patch("httpx.AsyncClient") as mock_client:
                client = await setup_http_client()
                mock_client.assert_called_once()
                # Check that proxy is in the client params
                args, kwargs = mock_client.call_args
                assert "proxy" in kwargs
                assert kwargs["proxy"] == "http://proxy.example.com"


@pytest.mark.asyncio
async def test_process_search_no_products():
    """Test process_search with no products found."""
    mock_client = AsyncMock()
    mock_search_crawler = MagicMock()
    mock_search_crawler.enqueue_product_urls = AsyncMock(return_value=0)

    with patch("src.main.setup_http_client", AsyncMock(return_value=mock_client)):
        with patch("src.main.Actor.open_request_queue", AsyncMock()):
            with patch("src.main.SearchCrawler", return_value=mock_search_crawler):
                result = await process_search("test query", 10)
                assert result == []
                mock_search_crawler.enqueue_product_urls.assert_called_once()


@pytest.mark.asyncio
async def test_main_missing_search_term():
    """Test main with missing search term."""
    with patch("src.main.Actor.get_input", AsyncMock(return_value={})):
        with pytest.raises(ValueError, match="search_term is required"):
            await main()


@pytest.mark.asyncio
async def test_main_with_search_term():
    """Test main with valid search term."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = "<html>Test page</html>"
    mock_client.get.return_value = mock_response

    with patch("src.main.Actor", AsyncMock()):
        with patch("src.main.Actor.get_input",
                  AsyncMock(return_value={"search_term": "test", "max_items": 5})):
            with patch("src.main.setup_http_client",
                      AsyncMock(return_value=mock_client)):
                with patch("src.main.paginate_search_results",
                          AsyncMock()) as mock_paginate:
                    await main()
                    # Check that paginate_search_results was called
                    assert mock_paginate.called
