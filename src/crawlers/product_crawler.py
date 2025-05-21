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

    def is_non_product_page(self, html: str, url: str) -> bool:
        """
        Check if the page is not a product page.

        Args:
            html: The HTML content of the page
            url: The URL of the page

        Returns:
            True if the page is not a product page, False otherwise
        """
        # Only filter out very specific non-product pages

        # Check for tracking page (very specific text)
        if "введи номер телефону для відстеження замовлення" in html.lower():
            logger.debug(f"Detected tracking page: {url}")
            return True

        # Check for specific non-product URLs
        if "/shipments" in url:
            logger.debug(f"Detected shipments page: {url}")
            return True

        # For product URLs, they should contain /p followed by numbers
        # But we'll only use this as a positive indicator, not to filter out
        if "/ua/p" in url and any(c.isdigit() for c in url):
            logger.debug(f"URL pattern indicates a product page: {url}")
            return False

        # If we have a product title and price, it's likely a product page
        if '<h1' in html and ('data-qaid="product_price"' in html or 'itemprop="price"' in html):
            logger.debug(f"Page has product title and price: {url}")
            return False

        # By default, assume it's a product page
        return False

    async def extract_prices_from_html(self, html: str) -> dict:
        """
        Extract price information from HTML.

        Args:
            html: The HTML content of the product page

        Returns:
            Dictionary with current_price, regular_price, and discounted_price
        """
        current_price = None
        regular_price = None
        discounted_price = None

        # Look for current price in various formats
        current_price_patterns = [
            r'data-qaid="product_price"[^>]*data-qaprice="([\d\s,.]+)"',  # Data attribute
            r'data-qaid="product_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Standard price
            r'data-qaid="product_price"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested
            r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
            r'itemprop="price"[^>]*content="([\d.,]+)"',  # Microdata format
        ]

        # Look for regular/old price (often shown as crossed-out)
        regular_price_patterns = [
            r'data-qaid="old_price"[^>]*data-qaprice="([\d\s,.]+)"',  # Data attribute
            r'data-qaid="old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
            r'data-qaid="product_old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
            r'class="[^"]*OldPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
            r'class="[^"]*crossed[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Crossed out
        ]

        # Extract current price
        for pattern in current_price_patterns:
            price_match = re.search(pattern, html)
            if price_match:
                price_str = price_match.group(1).strip()
                # Clean up price string
                price_str = price_str.replace(' ', '').replace(',', '.')
                try:
                    current_price = float(price_str)
                    logger.debug(f"Extracted current price from HTML: {current_price}")
                    break
                except ValueError:
                    continue

        # Extract regular price
        for pattern in regular_price_patterns:
            price_match = re.search(pattern, html)
            if price_match:
                price_str = price_match.group(1).strip()
                # Clean up price string
                price_str = price_str.replace(' ', '').replace(',', '.')
                try:
                    regular_price = float(price_str)
                    logger.debug(f"Extracted regular price from HTML: {regular_price}")
                    break
                except ValueError:
                    continue

        # Determine discounted price
        if regular_price is not None and current_price is not None:
            if regular_price > current_price:
                discounted_price = current_price
                logger.debug(
                    f"Detected discount from HTML: regular={regular_price}, "
                    f"discounted={discounted_price}"
                )
            else:
                # If regular <= current, something might be wrong with our extraction
                logger.debug(
                    f"Regular price ({regular_price}) <= current price ({current_price}), "
                    f"assuming no discount"
                )
                regular_price = current_price
                discounted_price = None

        return {
            "current_price": current_price,
            "regular_price": regular_price,
            "discounted_price": discounted_price
        }

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
        # First, validate that this is actually a product page
        if self.is_non_product_page(html, url):
            logger.warning(f"Skipping non-product page: {url}")
            return None

        # Extract JSON-LD data
        jsonld_data = await self.extract_jsonld_data(html)

        # Also extract price information from HTML to ensure we get both regular and discounted prices
        html_prices = await self.extract_prices_from_html(html)

        if not jsonld_data:
            # If JSON-LD extraction fails, try to extract data from HTML directly
            return await self.extract_data_from_html(html, url)

        # Extract basic product information from JSON-LD
        title = jsonld_data.get("name")

        # Extract price information from JSON-LD
        jsonld_price = None
        currency = None

        # Handle different offer structures
        offers = jsonld_data.get("offers", {})

        # Case 1: offers is a dictionary
        if isinstance(offers, dict):
            jsonld_price = offers.get("price")
            currency = offers.get("priceCurrency")
        # Case 2: offers is a list
        elif isinstance(offers, list) and offers:
            # Take the first offer
            first_offer = offers[0]
            if isinstance(first_offer, dict):
                jsonld_price = first_offer.get("price")
                currency = first_offer.get("priceCurrency")

        # Convert JSON-LD price to float if present
        if jsonld_price is not None:
            try:
                if isinstance(jsonld_price, str):
                    jsonld_price = jsonld_price.replace(',', '.').replace(' ', '')
                jsonld_price = float(jsonld_price)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert JSON-LD price to float: {jsonld_price}")
                jsonld_price = None

        # Combine JSON-LD and HTML price information
        html_regular_price = html_prices.get("regular_price")
        html_current_price = html_prices.get("current_price")

        # For price information, we need to combine JSON-LD and HTML data
        # First, check if HTML indicates a discount
        html_has_discount = (
            html_regular_price is not None and
            html_current_price is not None and
            html_regular_price > html_current_price * 1.01  # At least 1% difference
        )

        # For the regular price, always prioritize JSON-LD data if available
        # This is the most reliable approach for production use
        if jsonld_price is not None:
            # If we have JSON-LD price data, use it as the source of truth for regular price
            regular_price = jsonld_price
            logger.debug(f"Using JSON-LD price as regular price: {regular_price}")

            # For discounted price, check if HTML indicates a discount
            # and the current price is significantly lower than the JSON-LD price
            if (html_current_price is not None and
                jsonld_price > html_current_price * 1.01):  # At least 1% difference
                discounted_price = html_current_price
                logger.debug(
                    f"Using HTML current price as discounted price: {discounted_price}"
                )
            else:
                discounted_price = None
        elif html_has_discount:
            # If no JSON-LD but HTML shows a discount, use HTML data
            regular_price = html_regular_price
            discounted_price = html_current_price
            logger.debug(
                f"HTML indicates discount: regular={html_regular_price}, "
                f"discounted={html_current_price}"
            )
        elif html_regular_price is not None:
            # If no JSON-LD price and no HTML discount, fall back to HTML regular price
            regular_price = html_regular_price
            discounted_price = None
            logger.debug(f"Using HTML regular price: {regular_price}")
        else:
            # If neither is available, we have no regular price
            regular_price = None
            discounted_price = None

        # Default currency to UAH if not specified
        if not currency:
            currency = "UAH"

        # Extract image URL from JSON-LD
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

        # Extract seller information from JSON-LD
        seller_name = None
        seller_url = None
        if isinstance(offers, dict) and "seller" in offers:
            seller = offers.get("seller", {})
            if isinstance(seller, dict):
                seller_name = seller.get("name")
                # Try to extract seller URL from JSON-LD
                seller_url = seller.get("url")
                if seller_url and not seller_url.startswith('http'):
                    if seller_url.startswith('/'):
                        seller_url = f"https://prom.ua{seller_url}"
                    else:
                        seller_url = f"https://prom.ua/{seller_url}"

        # Extract availability status as a boolean from JSON-LD
        in_stock = None
        if isinstance(offers, dict) and "availability" in offers:
            availability = offers.get("availability", "")
            # Convert schema.org availability to boolean
            if "InStock" in availability:
                in_stock = True
            else:
                in_stock = False

        # Create and return Product object
        product = Product(
            url=url,
            title=title,
            regular_price_uah=regular_price,
            discounted_price_uah=discounted_price,
            currency=currency,
            image_url=image_url,
            seller_name=seller_name,
            seller_url=seller_url,
            in_stock=in_stock,
        )

        logger.info(
            f"Extracted product: {title} | "
            f"Regular: {regular_price} | Discounted: {discounted_price} | "
            f"Image: {image_url} | "
            f"Seller: {seller_name} | "
            f"In Stock: {in_stock} | "
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
                r'data-qaid="product_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Standard price
                r'data-qaid="product_price"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested span
                r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'class="[^"]*ProductPrice[^"]*"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested span
                r'itemprop="price"[^>]*content="([\d.,]+)"',  # Microdata format
                r'<div[^>]*class="[^"]*price[^"]*"[^>]*>([\d\s,.]+)[^<]*</div>',  # Generic price div
            ]

            # Look for regular price (often shown as crossed-out)
            regular_price_patterns = [
                r'data-qaid="old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price (exact match from example)
                r'data-qaid="product_old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
                r'class="[^"]*OldPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'class="[^"]*crossed[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Crossed out
                r'<span[^>]*style="[^"]*text-decoration:\s*line-through[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Styled as crossed-out
            ]

            # Save HTML snippets for debugging
            price_html_snippets = []

            # Extract current price
            current_price = None
            for pattern in current_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    # Save the HTML snippet for debugging
                    match_start = max(0, price_match.start() - 50)
                    match_end = min(len(html), price_match.end() + 50)
                    snippet = html[match_start:match_end]
                    price_html_snippets.append(f"Current price pattern: {pattern}\nMatch: {price_str}\nSnippet: {snippet}")

                    # Clean up price string
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        current_price = float(price_str)
                        logger.debug(f"Extracted current price: {current_price} from pattern: {pattern}")
                        break
                    except ValueError:
                        logger.debug(f"Failed to convert price string to float: {price_str}")
                        continue

            # Extract regular price
            regular_price = None
            for pattern in regular_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    # Save the HTML snippet for debugging
                    match_start = max(0, price_match.start() - 50)
                    match_end = min(len(html), price_match.end() + 50)
                    snippet = html[match_start:match_end]
                    price_html_snippets.append(f"Regular price pattern: {pattern}\nMatch: {price_str}\nSnippet: {snippet}")

                    # Clean up price string
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        regular_price = float(price_str)
                        logger.debug(f"Extracted regular price: {regular_price} from pattern: {pattern}")
                        break
                    except ValueError:
                        logger.debug(f"Failed to convert price string to float: {price_str}")
                        continue

            # Save price HTML snippets to a file for debugging
            if price_html_snippets:
                product_id = url.split('/')[-1].split('-')[0] if '/' in url else 'unknown'
                debug_file = f"debug_product_{product_id}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write("<html><body>\n")
                    f.write(f"<h1>Debug info for {url}</h1>\n")
                    f.write("<h2>Price HTML Snippets</h2>\n")
                    for i, snippet in enumerate(price_html_snippets):
                        f.write(f"<div style='margin-bottom: 20px; border: 1px solid #ccc; padding: 10px;'>\n")
                        f.write(f"<pre>{snippet}</pre>\n")
                        f.write("</div>\n")
                    f.write("</body></html>")
                logger.debug(f"Saved price HTML snippets to {debug_file}")

            # Determine discounted price
            discounted_price = None

            # If we have both prices and regular > current, then current is the discounted price
            if regular_price is not None and current_price is not None:
                if regular_price > current_price:
                    discounted_price = current_price
                    logger.debug(f"Detected discount: regular={regular_price}, discounted={discounted_price}")
                else:
                    # If regular <= current, something might be wrong with our extraction
                    # In this case, assume no discount
                    logger.debug(f"Regular price ({regular_price}) <= current price ({current_price}), assuming no discount")
                    regular_price = current_price
                    discounted_price = None
            # If we only have current_price, use it as regular_price
            elif regular_price is None and current_price is not None:
                logger.debug(f"Only current price ({current_price}) found, using as regular price")
                regular_price = current_price
                discounted_price = None
            # If we only have regular_price, use it as current_price too
            elif regular_price is not None and current_price is None:
                logger.debug(f"Only regular price ({regular_price}) found, using as current price")
                current_price = regular_price
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
                r'data-qaid="company_name"[^>]*>(.*?)</span>',  # Company name with span
                r'data-qaid="company_name"[^>]*>(.*?)</div>',   # Company name with div
                r'itemprop="name"[^>]*>(.*?)</span>',  # Microdata name
            ]

            for pattern in seller_patterns:
                seller_match = re.search(pattern, html)
                if seller_match:
                    seller_name = seller_match.group(1).strip()
                    # Clean up seller name (remove HTML tags)
                    seller_name = re.sub(r'<[^>]+>', '', seller_name)
                    logger.debug(f"Found seller name: {seller_name} with pattern: {pattern}")
                    break

            if not seller_name:
                logger.warning("Could not extract seller name from HTML")

            # Extract seller URL
            if seller_name:
                # Try multiple patterns to find seller URL
                seller_url_patterns = [
                    # Pattern for data-qaid="company_link" containing an anchor with the seller name
                    r'data-qaid="company_link"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>[^<]*' + re.escape(seller_name),
                    # Pattern for any anchor containing the seller name
                    r'<a[^>]+href="([^"]+)"[^>]*>[^<]*' + re.escape(seller_name),
                    # Pattern for company_link with any text
                    r'data-qaid="company_link"[^>]*>.*?<a[^>]+href="([^"]+)"',
                    # Pattern for seller profile link
                    r'<a[^>]+href="([^"]+)"[^>]*data-qaid="company_profile_link"',
                ]

                for pattern in seller_url_patterns:
                    seller_url_match = re.search(pattern, html)
                    if seller_url_match:
                        seller_url = seller_url_match.group(1).strip()
                        # Make sure it's an absolute URL
                        if not seller_url.startswith('http'):
                            if seller_url.startswith('/'):
                                seller_url = f"https://prom.ua{seller_url}"
                            else:
                                seller_url = f"https://prom.ua/{seller_url}"
                        logger.debug(f"Found seller URL: {seller_url}")
                        break

                # Log if we couldn't find a seller URL
                if not seller_url:
                    logger.warning(f"Could not extract seller URL for seller: {seller_name}")

            # Extract availability status as a boolean
            in_stock = None
            availability_patterns = [
                r'data-qaid="product_presence"[^>]*>(.*?)</span>',  # Standard format
                r'class="[^"]*ProductPresence[^"]*"[^>]*>(.*?)</span>',  # Alternative
                r'itemprop="availability"[^>]*content="([^"]+)"',  # Microdata
            ]

            for pattern in availability_patterns:
                availability_match = re.search(pattern, html)
                if availability_match:
                    availability_text = availability_match.group(1).strip()
                    # Clean up availability status (remove HTML tags)
                    availability_text = re.sub(r'<[^>]+>', '', availability_text)

                    # Convert to boolean
                    if "В наявності" in availability_text or "Готово до відправки" in availability_text:
                        in_stock = True
                    else:
                        in_stock = False
                    break

            # Default to False if we couldn't determine availability
            if in_stock is None:
                in_stock = False

            # If we couldn't extract the data, return None
            if not title and not current_price:
                logger.warning(f"Could not extract product data from HTML: {url}")
                return None

            # Create and return Product object
            product = Product(
                url=url,
                title=title,
                regular_price_uah=regular_price,
                discounted_price_uah=discounted_price,
                currency="UAH",  # Default currency for Prom.ua
                image_url=image_url,
                seller_name=seller_name,
                seller_url=seller_url,
                in_stock=in_stock,
            )

            logger.info(
                f"Extracted product from HTML: {title} | "
                f"Price: {current_price} UAH | "
                f"Regular: {regular_price} | Discounted: {discounted_price} | "
                f"Image: {image_url} | "
                f"Seller: {seller_name} | "
                f"In Stock: {in_stock} | "
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
