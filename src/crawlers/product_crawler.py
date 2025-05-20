"""
Product crawler for Prom.ua.

This module handles crawling product pages and extracting product data.
"""

import re
import json
from typing import Dict, Any, Optional, List, Union

import httpx
from loguru import logger
from apify import Actor

from src.config import JSONLD_REGEX
from src.utils.http import fetch_html
from src.models.product import Product


class ProductCrawler:
    """
    Crawler for Prom.ua product pages.

    This class handles crawling product pages and extracting product data.
    """

    def __init__(self, client: httpx.AsyncClient, session_id: Optional[str] = None):
        """
        Initialize the product crawler.

        Args:
            client: HTTPX client for making requests
            session_id: Optional session ID for logging
        """
        self.client = client
        self.session_id = session_id
        self.jsonld_pattern = re.compile(JSONLD_REGEX, re.DOTALL)

    async def extract_jsonld_data(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON-LD data from product page HTML.

        Args:
            html: The HTML content of the product page

        Returns:
            Extracted JSON-LD data as a dictionary, or None if not found
        """
        # Find JSON-LD script with Product type
        # Look for any script tag with type="application/ld+json"
        script_pattern = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
        scripts = script_pattern.findall(html)

        for script_content in scripts:
            try:
                # Parse JSON data
                data = json.loads(script_content)

                # Handle both single object and array of objects
                if isinstance(data, list):
                    # If it's an array, find the first Product object
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            logger.debug("Found Product in JSON-LD array")
                            return item
                elif isinstance(data, dict):
                    # If it's a single object and it's a Product
                    if data.get("@type") == "Product":
                        logger.debug("Found Product in JSON-LD object")
                        return data

            except json.JSONDecodeError as e:
                logger.warning(f"Error parsing JSON-LD script: {str(e)}")
                continue

        # If we get here, no Product data was found
        logger.warning("No JSON-LD Product data found in HTML")
        return None

    async def extract_product_data(
        self, html: str, url: str
    ) -> Optional[Product]:
        """
        Extract product data from product page HTML.

        Args:
            html: The HTML content of the product page
            url: The URL of the product page

        Returns:
            Product object with extracted data, or None if extraction failed
        """
        # Extract JSON-LD data
        jsonld_data = await self.extract_jsonld_data(html)
        if not jsonld_data:
            # If JSON-LD extraction fails, try to extract data from HTML directly
            return await self.extract_data_from_html(html, url)

        # Extract basic product information
        title = jsonld_data.get("name")

        # Extract price information
        price = None
        currency = None

        # Handle different offer structures
        offers = jsonld_data.get("offers", {})

        # Case 1: offers is a dictionary
        if isinstance(offers, dict):
            price = offers.get("price")
            currency = offers.get("priceCurrency")

        # Case 2: offers is a list
        elif isinstance(offers, list) and offers:
            # Take the first offer
            first_offer = offers[0]
            if isinstance(first_offer, dict):
                price = first_offer.get("price")
                currency = first_offer.get("priceCurrency")

        # Convert price to float if present
        if price is not None:
            try:
                # Handle price as string with commas or spaces
                if isinstance(price, str):
                    price = price.replace(',', '.').replace(' ', '')
                price = float(price)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert price to float: {price}")
                price = None

        # Default currency to UAH if not specified
        if not currency and price is not None:
            currency = "UAH"

        # Create and return Product object
        product = Product(
            url=url,
            title=title,
            price_uah=price,
            currency=currency,
        )

        logger.info(
            f"Extracted product: {title} | "
            f"Price: {price} {currency} | URL: {url}"
        )

        return product

    async def extract_data_from_html(self, html: str, url: str) -> Optional[Product]:
        """
        Extract product data directly from HTML when JSON-LD is not available.

        Args:
            html: The HTML content of the product page
            url: The URL of the product page

        Returns:
            Product object with extracted data, or None if extraction failed
        """
        try:
            # Extract title
            title_pattern = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
            title_match = title_pattern.search(html)
            title = title_match.group(1).strip() if title_match else None

            # Clean up title (remove HTML tags)
            if title:
                title = re.sub(r'<[^>]+>', '', title)

            # Extract price
            # Look for price in various formats
            price_patterns = [
                r'data-qaid="product_price"[^>]*>([\d\s,.]+)</span>',  # Standard price
                r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)</span>',  # Alternative format
                r'itemprop="price"[^>]*content="([\d.]+)"',  # Microdata format
            ]

            price = None
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    # Clean up price string
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        price = float(price_str)
                        break
                    except ValueError:
                        continue

            # If we couldn't extract the data, return None
            if not title and not price:
                logger.warning(f"Could not extract product data from HTML: {url}")
                return None

            # Create and return Product object
            product = Product(
                url=url,
                title=title,
                price_uah=price,
                currency="UAH",  # Default currency for Prom.ua
            )

            logger.info(
                f"Extracted product from HTML: {title} | "
                f"Price: {price} UAH | URL: {url}"
            )

            return product

        except Exception as e:
            logger.error(f"Error extracting product data from HTML: {str(e)}")
            return None

    async def process_product_page(self, url: str) -> Optional[Product]:
        """
        Process a product page and extract product data.

        Args:
            url: The URL of the product page

        Returns:
            Product object with extracted data, or None if processing failed
        """
        try:
            # Fetch the product page
            html = await fetch_html(self.client, url, self.session_id)

            # Extract product data
            product = await self.extract_product_data(html, url)

            if not product:
                logger.warning(f"Failed to extract product data from {url}")
                return None

            return product

        except Exception as e:
            logger.error(f"Error processing product page {url}: {str(e)}")
            return None
