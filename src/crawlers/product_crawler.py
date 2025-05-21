"""
Product crawler for Prom.ua.

This module handles crawling product pages and extracting product data.
"""

import re
from typing import Optional

import httpx
from loguru import logger

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
            Dictionary with regular_price and discounted_price
        """
        regular_price = None
        discounted_price = None

        # First, try to extract prices from data-qaprice attributes which are most reliable
        # Look for the current selling price
        current_price_attr_pattern = r'data-qaid="product_price"[^>]*data-qaprice="([\d\s,.]+)"'
        current_price_match = re.search(current_price_attr_pattern, html)

        # Look for the old price (crossed-out price)
        old_price_attr_pattern = r'data-qaid="old_price"[^>]*data-qaprice="([\d\s,.]+)"'
        old_price_match = re.search(old_price_attr_pattern, html)

        # Process current price from attribute
        current_price = None
        if current_price_match:
            price_str = current_price_match.group(1).strip()
            price_str = price_str.replace(' ', '').replace(',', '.')
            try:
                current_price = float(price_str)
                logger.debug(f"Extracted current price from data-qaprice attribute: {current_price}")
            except ValueError:
                logger.warning(f"Failed to convert current price string to float: {price_str}")

        # Process old price from attribute
        old_price = None
        if old_price_match:
            price_str = old_price_match.group(1).strip()
            price_str = price_str.replace(' ', '').replace(',', '.')
            try:
                old_price = float(price_str)
                logger.debug(f"Extracted old price from data-qaprice attribute: {old_price}")
                # If we have both prices and old price is different from current price,
                # determine if this is a discount
                if current_price is not None and abs(old_price - current_price) > 0.01:
                    # In a normal discount scenario, old_price > current_price
                    if old_price > current_price:
                        logger.debug(f"Normal discount: old_price ({old_price}) > current_price ({current_price})")
                    else:
                        # In some cases, the old_price might be lower than current_price
                        # This is not a discount, but we'll still record both prices
                        logger.debug(f"Unusual price pattern: old_price ({old_price}) < current_price ({current_price})")
            except ValueError:
                logger.warning(f"Failed to convert old price string to float: {price_str}")

        # If we couldn't find prices from attributes, try extracting from HTML content
        if current_price is None:
            # Look for current price in various formats
            current_price_patterns = [
                r'data-qaid="product_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Standard price
                r'data-qaid="product_price"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested
                r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'itemprop="price"[^>]*content="([\d.,]+)"',  # Microdata format
            ]

            for pattern in current_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        current_price = float(price_str)
                        logger.debug(f"Extracted current price from HTML content: {current_price}")
                        break
                    except ValueError:
                        continue

        if old_price is None:
            # Look for old price (often shown as crossed-out)
            old_price_patterns = [
                r'data-qaid="old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
                r'data-qaid="product_old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
                r'class="[^"]*OldPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'class="[^"]*crossed[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Crossed out
            ]

            for pattern in old_price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    price_str = price_match.group(1).strip()
                    price_str = price_str.replace(' ', '').replace(',', '.')
                    try:
                        old_price = float(price_str)
                        logger.debug(f"Extracted old price from HTML content: {old_price}")
                        # If we have both prices and old price is higher, it's a discount
                        if current_price is not None and old_price > current_price:
                            logger.debug("Discount detected in HTML content")
                        break
                    except ValueError:
                        continue

        # Determine regular and discounted prices based on what we found
        if old_price is not None and current_price is not None:
            # We have both old_price and current_price
            if old_price > current_price:
                # This is a discount: old_price is regular_price, current_price is discounted_price
                regular_price = old_price
                discounted_price = current_price
                logger.debug(f"Product has a discount: regular={regular_price}, discounted={discounted_price}")
            else:
                # If old_price <= current_price, this is not a discount
                # Use current_price as regular_price
                regular_price = current_price
                discounted_price = None
                logger.debug(f"No discount: current_price ({current_price}) >= old_price ({old_price})")
        else:
            # If we only have current_price, use it as regular_price
            regular_price = current_price
            discounted_price = None
            logger.debug(f"No old price: using current_price ({current_price}) as regular_price")

        # Handle edge cases
        if regular_price is None and current_price is not None:
            # If we couldn't determine regular price but have current price, use it as regular price
            regular_price = current_price
            logger.debug(f"Using current price as regular price: {regular_price}")

        # Final validation
        if regular_price is None:
            logger.warning("Could not extract any price information from HTML")

        return {
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

        # Extract all product data directly from HTML
        return await self.extract_data_from_html(html, url)

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

            # First, try to extract prices from data-qaprice attributes which are most reliable
            # Look for the current selling price
            current_price_attr_pattern = r'data-qaid="product_price"[^>]*data-qaprice="([\d\s,.]+)"'
            current_price_match = re.search(current_price_attr_pattern, html)

            # Look for the old price (crossed-out price)
            old_price_attr_pattern = r'data-qaid="old_price"[^>]*data-qaprice="([\d\s,.]+)"'
            old_price_match = re.search(old_price_attr_pattern, html)

            # Process current price from attribute
            current_price = None
            if current_price_match:
                price_str = current_price_match.group(1).strip()
                price_str = price_str.replace(' ', '').replace(',', '.')
                try:
                    current_price = float(price_str)
                    logger.debug(f"Extracted current price from data-qaprice attribute: {current_price}")
                except ValueError:
                    logger.warning(f"Failed to convert current price string to float: {price_str}")

            # Process old price from attribute
            old_price = None
            if old_price_match:
                price_str = old_price_match.group(1).strip()
                price_str = price_str.replace(' ', '').replace(',', '.')
                try:
                    old_price = float(price_str)
                    logger.debug(f"Extracted old price from data-qaprice attribute: {old_price}")
                    # If we have both prices and old price is different from current price,
                    # determine if this is a discount
                    if current_price is not None and abs(old_price - current_price) > 0.01:
                        # In a normal discount scenario, old_price > current_price
                        if old_price > current_price:
                            logger.debug(f"Normal discount: old_price ({old_price}) > current_price ({current_price})")
                        else:
                            # In some cases, the old_price might be lower than current_price
                            # This is not a discount, but we'll still record both prices
                            logger.debug(f"Unusual price pattern: old_price ({old_price}) < current_price ({current_price})")
                except ValueError:
                    logger.warning(f"Failed to convert old price string to float: {price_str}")

            # Define patterns for price extraction
            current_price_patterns = [
                r'data-qaid="product_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Standard price
                r'data-qaid="product_price"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested span
                r'class="[^"]*ProductPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'class="[^"]*ProductPrice[^"]*"[^>]*>.*?<span[^>]*>([\d\s,.]+)[^<]*</span>',  # Nested span
                r'itemprop="price"[^>]*content="([\d.,]+)"',  # Microdata format
                r'<div[^>]*class="[^"]*price[^"]*"[^>]*>([\d\s,.]+)[^<]*</div>',  # Generic price div
            ]

            regular_price_patterns = [
                r'data-qaid="old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price (exact match from example)
                r'data-qaid="product_old_price"[^>]*>([\d\s,.]+)[^<]*</span>',  # Old price
                r'class="[^"]*OldPrice[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Alternative
                r'class="[^"]*crossed[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Crossed out
                r'<span[^>]*style="[^"]*text-decoration:\s*line-through[^"]*"[^>]*>([\d\s,.]+)[^<]*</span>',  # Styled as crossed-out
            ]

            # Save HTML snippets for debugging
            price_html_snippets = []

            # If we couldn't find prices from attributes, try extracting from HTML content
            if current_price is None:
                # Extract current price from HTML content
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

            # Log price HTML snippets for debugging at debug level
            if price_html_snippets:
                for i, snippet in enumerate(price_html_snippets):
                    logger.debug(f"Price HTML snippet {i+1}: {snippet[:100]}...")

            # Determine regular and discounted prices based on what we found
            if old_price is not None and current_price is not None:
                # We have both old_price and current_price
                if old_price > current_price:
                    # This is a discount: old_price is regular_price, current_price is discounted_price
                    regular_price = old_price
                    discounted_price = current_price
                    logger.debug(f"Product has a discount: regular={regular_price}, discounted={discounted_price}")
                else:
                    # If old_price <= current_price, this is not a discount
                    # Use current_price as regular_price
                    regular_price = current_price
                    discounted_price = None
                    logger.debug(f"No discount: current_price ({current_price}) >= old_price ({old_price})")
            else:
                # If we only have current_price, use it as regular_price
                regular_price = current_price
                discounted_price = None
                logger.debug(f"No old price: using current_price ({current_price}) as regular_price")

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
