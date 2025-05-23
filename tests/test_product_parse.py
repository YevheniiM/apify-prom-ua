"""
Tests for product data extraction functionality.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from src.crawlers.product_crawler import ProductCrawler
from src.models.product import Product


# Sample JSON-LD data for testing
SAMPLE_JSONLD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Product</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Test Product Name",
        "offers": {
            "@type": "Offer",
            "price": "199.99",
            "priceCurrency": "UAH"
        }
    }
    </script>
</head>
<body>
    <h1>Product Page</h1>
</body>
</html>
"""

# Sample JSON-LD data with offers as a list
SAMPLE_JSONLD_HTML_LIST_OFFERS = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Product</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Test Product With List Offers",
        "offers": [
            {
                "@type": "Offer",
                "price": "299.99",
                "priceCurrency": "UAH"
            },
            {
                "@type": "Offer",
                "price": "289.99",
                "priceCurrency": "UAH"
            }
        ]
    }
    </script>
</head>
<body>
    <h1>Product Page</h1>
</body>
</html>
"""

# Sample HTML with no JSON-LD data
SAMPLE_HTML_NO_JSONLD = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Product No JSON-LD</title>
</head>
<body>
    <h1>Product Page</h1>
</body>
</html>
"""


@pytest.fixture
def product_crawler():
    """Create a ProductCrawler instance for testing."""
    client_mock = MagicMock()
    return ProductCrawler(client_mock, "test-session")


@pytest.mark.asyncio
async def test_extract_jsonld_data(product_crawler):
    """Test extracting JSON-LD data from HTML."""
    # Test with valid JSON-LD
    data = await product_crawler.extract_jsonld_data(SAMPLE_JSONLD_HTML)
    assert data is not None
    assert data["@type"] == "Product"
    assert data["name"] == "Test Product Name"
    assert data["offers"]["price"] == "199.99"

    # Test with no JSON-LD
    data = await product_crawler.extract_jsonld_data(SAMPLE_HTML_NO_JSONLD)
    assert data is None


@pytest.mark.asyncio
async def test_extract_product_data_single_offer(product_crawler):
    """Test extracting product data with a single offer."""
    product = await product_crawler.extract_product_data(
        SAMPLE_JSONLD_HTML, "https://example.com/product"
    )

    assert isinstance(product, Product)
    assert product.title == "Test Product Name"
    assert product.price_uah == 199.99
    assert product.currency == "UAH"
    assert product.url == "https://example.com/product"


@pytest.mark.asyncio
async def test_extract_product_data_list_offers(product_crawler):
    """Test extracting product data with offers as a list."""
    product = await product_crawler.extract_product_data(
        SAMPLE_JSONLD_HTML_LIST_OFFERS, "https://example.com/product2"
    )

    assert isinstance(product, Product)
    assert product.title == "Test Product With List Offers"
    assert product.price_uah == 299.99  # Should take the first offer
    assert product.currency == "UAH"
    assert product.url == "https://example.com/product2"


@pytest.mark.asyncio
async def test_extract_product_data_no_jsonld(product_crawler):
    """Test extracting product data with no JSON-LD data."""
    # Mock the extract_data_from_html method to return None
    with patch.object(product_crawler, 'extract_data_from_html', return_value=None):
        product = await product_crawler.extract_product_data(
            SAMPLE_HTML_NO_JSONLD, "https://example.com/product3"
        )

        assert product is None


@pytest.mark.asyncio
async def test_process_product_page(product_crawler):
    """Test processing a product page."""
    # Mock the fetch_html function
    with patch("src.crawlers.product_crawler.fetch_html",
               return_value=SAMPLE_JSONLD_HTML):
        product = await product_crawler.process_product_page(
            "https://example.com/product"
        )

        assert isinstance(product, Product)
        assert product.title == "Test Product Name"
        assert product.price_uah == 199.99
