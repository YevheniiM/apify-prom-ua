"""
Product crawler for Prom.ua.

This module handles crawling product pages and extracting product data.
"""

import re
import json
from typing import Dict, Any, Optional

import httpx
from loguru import logger

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
        regular_price = None
        discounted_price = None
        current_price = None
        currency = None

        # Handle different offer structures
        offers = jsonld_data.get("offers", {})

        # Case 1: offers is a dictionary
        if isinstance(offers, dict):
            current_price = offers.get("price")
            currency = offers.get("priceCurrency")

            # Check for price specification with multiple prices
            price_specification = offers.get("priceSpecification", [])
            if isinstance(price_specification, list) and price_specification:
                for spec in price_specification:
                    if isinstance(spec, dict):
                        price_type = spec.get("valueAddedTaxIncluded", True)
                        if price_type:
                            # This is the regular price
                            regular_price = spec.get("price")
                        else:
                            # This might be a discounted price
                            discounted_price = spec.get("price")

            # Check for high and low prices
            high_price = offers.get("highPrice")
            low_price = offers.get("lowPrice")
            if high_price and low_price:
                regular_price = high_price
                discounted_price = low_price

        # Case 2: offers is a list
        elif isinstance(offers, list) and offers:
            # Take the first offer
            first_offer = offers[0]
            if isinstance(first_offer, dict):
                current_price = first_offer.get("price")
                currency = first_offer.get("priceCurrency")

                # Check for price specification
                price_specification = first_offer.get("priceSpecification", [])
                if isinstance(price_specification, list) and price_specification:
                    for spec in price_specification:
                        if isinstance(spec, dict):
                            price_type = spec.get("valueAddedTaxIncluded", True)
                            if price_type:
                                regular_price = spec.get("price")
                            else:
                                discounted_price = spec.get("price")

        # Convert prices to float if present
        for price_var, price_val in [
            ("current_price", current_price),
            ("regular_price", regular_price),
            ("discounted_price", discounted_price)
        ]:
            if price_val is not None:
                try:
                    # Handle price as string with commas or spaces
                    if isinstance(price_val, str):
                        price_val = price_val.replace(',', '.').replace(' ', '')
                    price_val = float(price_val)

                    # Update the variable
                    if price_var == "current_price":
                        current_price = price_val
                    elif price_var == "regular_price":
                        regular_price = price_val
                    elif price_var == "discounted_price":
                        discounted_price = price_val

                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {price_var} to float: {price_val}")
                    if price_var == "current_price":
                        current_price = None
                    elif price_var == "regular_price":
                        regular_price = None
                    elif price_var == "discounted_price":
                        discounted_price = None

        # If we only have current_price but not regular_price, use current_price as regular_price
        if regular_price is None and current_price is not None:
            regular_price = current_price

        # If we have both regular_price and discounted_price, use discounted_price as current_price
        if regular_price is not None and discounted_price is not None:
            current_price = discounted_price
        # If we only have regular_price, use it as current_price
        elif regular_price is not None and current_price is None:
            current_price = regular_price

        # Default currency to UAH if not specified
        if not currency and (current_price is not None or regular_price is not None or discounted_price is not None):
            currency = "UAH"

        # Extract image URL
        image_url = None
        if "image" in jsonld_data:
            # Handle both string and array image formats
            image_data = jsonld_data.get("image")
            if isinstance(image_data, str):
                image_url = image_data
            elif isinstance(image_data, list) and image_data:
                # Take the first image
                image_url = image_data[0] if isinstance(image_data[0], str) else None
            elif isinstance(image_data, dict) and "url" in image_data:
                # Handle ImageObject format
                image_url = image_data.get("url")

        # Extract seller information
        seller_name = None
        seller_url = None
        offers = jsonld_data.get("offers", {})
        if isinstance(offers, dict) and "seller" in offers:
            seller = offers.get("seller", {})
            if isinstance(seller, dict):
                seller_name = seller.get("name")

        # Extract availability status
        availability_status = None
        if isinstance(offers, dict) and "availability" in offers:
            availability = offers.get("availability", "")
            # Convert schema.org availability to human-readable format
            if "InStock" in availability:
                availability_status = "В наявності"
            elif "OutOfStock" in availability:
                availability_status = "Немає в наявності"
            elif "PreOrder" in availability:
                availability_status = "Передзамовлення"
            else:
                availability_status = availability.split("/")[-1] if "/" in availability else availability

        # Create and return Product object
        product = Product(
            url=url,
            title=title,
            price_uah=current_price,  # For backward compatibility
            regular_price_uah=regular_price,
            discounted_price_uah=discounted_price,
            currency=currency,
            image_url=image_url,
            seller_name=seller_name,
            seller_url=seller_url,
            availability_status=availability_status,
        )

        logger.info(
            f"Extracted product: {title} | "
            f"Price: {current_price} {currency} | "
            f"Regular: {regular_price} | Discounted: {discounted_price} | "
            f"Image: {image_url} | "
            f"Seller: {seller_name} | "
            f"Availability: {availability_status} | "
            f"URL: {url}"
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

            # Extract prices
            # Look for current price in various formats
            current_price_patterns = [
                r'data-qaid="product_price"[^>]*>([\d\s,.]+)</span>',  # Standard price
                r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)</span>',  # Alternative
                r'itemprop="price"[^>]*content="([\d.]+)"',  # Microdata format
            ]

            # Look for regular price (often shown as crossed-out)
            regular_price_patterns = [
                r'data-qaid="product_old_price"[^>]*>([\d\s,.]+)</span>',  # Old price
                r'class="[^"]*OldPrice[^"]*"[^>]*>([\d\s,.]+)</span>',  # Alternative
                r'class="[^"]*crossed[^"]*"[^>]*>([\d\s,.]+)</span>',  # Crossed out
            ]

            # Extract current price
            current_price = None
            for pattern in current_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    # Clean up price string
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        current_price = float(price_str)
                        break
                    except ValueError:
                        continue

            # Extract regular price
            regular_price = None
            for pattern in regular_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    # Clean up price string
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        regular_price = float(price_str)
                        break
                    except ValueError:
                        continue

            # If we have current_price but not regular_price, use current_price as regular_price
            if regular_price is None and current_price is not None:
                regular_price = current_price
                discounted_price = None
            # If we have both, current_price is the discounted price
            elif regular_price is not None and current_price is not None and regular_price > current_price:
                discounted_price = current_price
            else:
                discounted_price = None

            # Extract image URL
            image_url = None
            image_patterns = [
                r'<meta\s+property="og:image"\s+content="([^"]+)"',  # Open Graph image
                r'<img[^>]+data-qaid="product_image"[^>]+src="([^"]+)"',  # Product image
                r'<img[^>]+class="[^"]*ProductImage[^"]*"[^>]+src="([^"]+)"',  # Alternative
                r'<img[^>]+itemprop="image"[^>]+src="([^"]+)"',  # Microdata image
            ]

            for pattern in image_patterns:
                image_match = re.search(pattern, html)
                if image_match:
                    image_url = image_match.group(1).strip()
                    break

            # Extract seller information
            seller_name = None
            seller_url = None
            seller_patterns = [
                r'data-qaid="company_name"[^>]*>(.*?)</span>',  # Company name
                r'itemprop="name"[^>]*>(.*?)</span>',  # Microdata name
            ]

            for pattern in seller_patterns:
                seller_match = re.search(pattern, html)
                if seller_match:
                    seller_name = seller_match.group(1).strip()
                    # Clean up seller name (remove HTML tags)
                    seller_name = re.sub(r'<[^>]+>', '', seller_name)
                    break

            # Extract seller URL
            if seller_name:
                seller_url_pattern = r'<a[^>]+href="([^"]+)"[^>]*>[^<]*' + re.escape(seller_name)
                seller_url_match = re.search(seller_url_pattern, html)
                if seller_url_match:
                    seller_url = seller_url_match.group(1).strip()
                    # Make sure it's an absolute URL
                    if not seller_url.startswith('http'):
                        seller_url = f"https://prom.ua{seller_url}"

            # Extract availability status
            availability_status = None
            availability_patterns = [
                r'data-qaid="product_presence"[^>]*>(.*?)</span>',  # Standard format
                r'class="[^"]*ProductPresence[^"]*"[^>]*>(.*?)</span>',  # Alternative
                r'itemprop="availability"[^>]*content="([^"]+)"',  # Microdata
            ]

            for pattern in availability_patterns:
                availability_match = re.search(pattern, html)
                if availability_match:
                    availability_status = availability_match.group(1).strip()
                    # Clean up availability status (remove HTML tags)
                    availability_status = re.sub(r'<[^>]+>', '', availability_status)
                    break

            # If we couldn't extract the data, return None
            if not title and not current_price:
                logger.warning(f"Could not extract product data from HTML: {url}")
                return None

            # Create and return Product object
            product = Product(
                url=url,
                title=title,
                price_uah=current_price,  # For backward compatibility
                regular_price_uah=regular_price,
                discounted_price_uah=discounted_price,
                currency="UAH",  # Default currency for Prom.ua
                image_url=image_url,
                seller_name=seller_name,
                seller_url=seller_url,
                availability_status=availability_status,
            )

            logger.info(
                f"Extracted product from HTML: {title} | "
                f"Price: {current_price} UAH | "
                f"Regular: {regular_price} | Discounted: {discounted_price} | "
                f"Image: {image_url} | "
                f"Seller: {seller_name} | "
                f"Availability: {availability_status} | "
                f"URL: {url}"
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
