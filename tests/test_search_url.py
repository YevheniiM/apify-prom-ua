"""
Tests for search URL building functionality.
"""

import pytest
from src.utils.http import build_search_url


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
