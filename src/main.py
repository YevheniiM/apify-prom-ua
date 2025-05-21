"""
Main entry point for the Prom.ua search crawler Apify actor.

This module sets up the actor, initializes the request queue,
and orchestrates the crawling process.
"""

import asyncio
import uuid
import sys
import re
import random
from typing import Dict, Any, List
from urllib.parse import urljoin

import httpx
from loguru import logger
from apify import Actor
from bs4 import BeautifulSoup

from src.config import (
    PROXY_CONFIG,
    REQUEST_TIMEOUT,
    MAX_PAGES,
)
from src.crawlers.search_crawler import SearchCrawler
from src.crawlers.product_crawler import ProductCrawler
from src.utils.http import build_search_url


async def setup_http_client() -> httpx.AsyncClient:
    """
    Set up an HTTPX client with proxy configuration.

    Returns:
        Configured HTTPX client
    """
    # Get proxy URL from Apify if enabled
    proxy_url = None
    if PROXY_CONFIG["useApifyProxy"]:
        try:
            proxy_configuration = await Actor.create_proxy_configuration(
                groups=PROXY_CONFIG["apifyProxyGroups"]
            )
            proxy_url = await proxy_configuration.new_url()
            logger.info(f"Using Apify proxy: {proxy_url}")
        except Exception as e:
            logger.warning(f"Failed to set up Apify proxy: {str(e)}")
            logger.info("Continuing without proxy")
    else:
        logger.info("Proxy disabled in config, continuing without proxy")

    # Create and return the client
    client_params = {
        "timeout": REQUEST_TIMEOUT,
        "follow_redirects": True,
        "http2": True,  # Enable HTTP/2 for better performance
    }

    # Add proxy if available
    if proxy_url:
        client_params["proxy"] = proxy_url

    return httpx.AsyncClient(**client_params)


async def extract_products_direct(
    client: httpx.AsyncClient,
    search_term: str,
    max_items: int,
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Extract products directly from search results page.

    This is a fallback method when the queue-based approach fails.

    Args:
        client: HTTPX client for making requests
        search_term: The search query
        max_items: Maximum number of products to collect
        session_id: Session ID for logging

    Returns:
        List of product data dictionaries
    """
    try:
        # Build the search URL
        search_url = build_search_url(search_term, 1)
        logger.info(f"Using direct approach for '{search_term}' [Session: {session_id}]")

        # Define browser-like headers
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Fetch the search page
        response = await client.get(
            search_url,
            headers=headers,
            follow_redirects=True
        )

        # Extract product URLs using regex
        product_pattern = re.compile(r'href="(/ua/p[^"]+)"')

        # Extract and normalize URLs
        product_urls = []
        for match in product_pattern.finditer(response.text):
            relative_url = match.group(1)
            if "product-opinions" in relative_url:
                continue
            absolute_url = urljoin(search_url, relative_url)
            product_urls.append(absolute_url)

        # Remove duplicates and limit to max_items
        product_urls = list(dict.fromkeys(product_urls))[:max_items]

        if not product_urls:
            logger.warning("No product URLs found with direct approach")
            return []

        logger.info(
            f"Found {len(product_urls)} product URLs with direct approach"
        )

        # Extract product data from the search results page
        products = []

        # Define regex patterns for extraction
        title_pattern = re.compile(r'data-qaid="product_name"[^>]*>([^<]+)')
        price_pattern = re.compile(
            r'data-qaid="product_price"[^>]*data-qaprice="([^"]+)"'
        )

        # Extract titles and prices
        titles = title_pattern.findall(response.text)
        prices = price_pattern.findall(response.text)

        logger.info(f"Found {len(titles)} titles and {len(prices)} prices")

        # Determine how many products we can process
        max_products = min(
            len(product_urls), len(titles), len(prices), max_items
        )

        # Import here to avoid circular imports
        from src.models.product import Product

        # Process each product
        for i in range(max_products):
            url = product_urls[i]

            # Clean up title (remove HTML entities)
            title = titles[i].strip()
            title = title.replace('&quot;', '"').replace('&amp;', '&')

            # Clean up price string and convert to float
            price_str = prices[i].strip().replace(' ', '').replace(',', '.')
            try:
                price = float(price_str)
            except ValueError:
                price = None

            # Create product object
            product = Product(
                url=url,
                title=title,
                price_uah=price,
                currency="UAH"
            )

            # Convert to dictionary and add to results
            product_data = product.to_dict()
            products.append(product_data)

            logger.info(f"Processed product: {title} - {price} UAH")

        return products

    except Exception as e:
        logger.error(f"Direct extraction failed: {str(e)}")
        return []


async def process_search(
    search_term: str, max_items: int
) -> List[Dict[str, Any]]:
    """
    Process a search query and collect product data.

    Args:
        search_term: The search query
        max_items: Maximum number of products to collect

    Returns:
        List of product data dictionaries
    """
    # Create a session ID for logging
    session_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting search for '{search_term}' with session {session_id}")

    # Initialize request queue
    request_queue = await Actor.open_request_queue()

    # Set up HTTP client
    async with await setup_http_client() as client:
        # Initialize search crawler
        search_crawler = SearchCrawler(client, session_id)

        try:
            # Enqueue product URLs
            enqueued_count = await search_crawler.enqueue_product_urls(
                search_term, max_items, request_queue
            )

            if enqueued_count == 0:
                logger.warning(
                    f"No products found for search term: {search_term}"
                )
                return []

        except Exception as e:
            logger.error(f"Error enqueueing product URLs: {str(e)}")
            # Try direct approach as fallback
            return await extract_products_direct(
                client, search_term, max_items, session_id
            )

        # Process product pages from the queue
        return await process_product_queue(
            client, request_queue, enqueued_count, session_id
        )


async def process_product_queue(
    client: httpx.AsyncClient,
    request_queue: Any,
    enqueued_count: int,
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Process product pages from the request queue.

    Args:
        client: HTTPX client for making requests
        request_queue: Apify request queue
        enqueued_count: Number of requests in the queue
        session_id: Session ID for logging

    Returns:
        List of product data dictionaries
    """
    products = []
    processed_count = 0
    failed_count = 0

    # Initialize product crawler
    product_crawler = ProductCrawler(client, session_id)

    # Process requests from the queue
    while processed_count + failed_count < enqueued_count:
        # Get next request from queue
        request = await request_queue.fetch_next_request()
        if not request:
            logger.info("No more requests in the queue")
            break

        try:
            # Process the product page
            if request.user_data.get("label") == "PRODUCT":
                # Process the product page
                url = request.url
                product = await product_crawler.process_product_page(url)

                if product:
                    # Convert product to dictionary and add to results
                    product_data = product.to_dict()
                    products.append(product_data)
                    processed_count += 1

                    logger.info(
                        f"Processed {processed_count}/{enqueued_count}: "
                        f"{product.title or 'Unknown'}"
                    )
                else:
                    failed_count += 1
                    logger.warning(f"Failed to process product {request.url}")

            # Mark request as handled
            await request_queue.mark_request_as_handled(request)

        except Exception as e:
            # Log error and mark request as failed
            logger.error(f"Error processing request {request.url}: {str(e)}")
            await request_queue.reclaim_request(request)
            failed_count += 1

    # Log summary
    logger.info(
        f"Search completed. Processed {processed_count} products, "
        f"failed {failed_count} products."
    )

    return products


async def paginate_search_results(
    client: httpx.AsyncClient,
    search_term: str,
    max_items: int
) -> List[Dict[str, Any]]:
    """
    Paginate through search results and extract product data.

    Args:
        client: HTTPX client for making requests
        search_term: The search query
        max_items: Maximum number of products to collect

    Returns:
        List of product data dictionaries
    """
    try:
        # Define common headers for all requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Initialize variables for pagination
        current_page = 1
        all_products = []

        # Define patterns for extraction
        title_pattern = re.compile(r'data-qaid="product_name"[^>]*>([^<]+)')
        price_pattern = re.compile(
            r'data-qaid="product_price"[^>]*data-qaprice="([^"]+)"'
        )

        # Import here to avoid circular imports
        from src.models.product import Product

        # Process pages until we have enough products or reach the max page limit
        while len(all_products) < max_items and current_page <= MAX_PAGES:
            # Build the search URL for the current page
            search_url = build_search_url(search_term, current_page)
            logger.info(f"Processing page {current_page}: {search_url}")

            # Fetch the search page
            response = await client.get(
                search_url,
                headers=headers,
                follow_redirects=True
            )

            # Extract product URLs from the current page using BeautifulSoup
            # This is a more robust approach than using regex patterns
            page_product_urls = []

            # Parse the HTML with BeautifulSoup
            html_soup = BeautifulSoup(response.text, 'html.parser')

            # Find all links on the page
            all_links = html_soup.find_all('a', href=True)

            # Filter for potential product links
            for link in all_links:
                href = link.get('href', '')
                # Check if it looks like a product link
                if '/ua/' in href and not any(x in href for x in [
                    'search', 'category', 'login', 'register', 'cart', 'checkout'
                ]):
                    # Convert relative URLs to absolute
                    if href.startswith('http'):
                        absolute_url = href
                    else:
                        absolute_url = urljoin(search_url, href)
                    page_product_urls.append(absolute_url)

            # Extract titles and prices
            titles = title_pattern.findall(response.text)
            prices = price_pattern.findall(response.text)

            # If we couldn't find any product URLs, log an error
            if not page_product_urls:
                logger.error(
                    "Failed to extract product URLs. "
                    "Site structure may have changed."
                )
                # Save a sample of the HTML for debugging
                with open(f"debug_html_page_{current_page}.html", "w") as f:
                    f.write(response.text[:10000])  # Save first 10K chars

                # Skip this page and try the next one
                continue

            # Remove duplicates
            page_product_urls = list(dict.fromkeys(page_product_urls))

            # Extract titles and prices from the current page
            titles = title_pattern.findall(response.text)
            prices = price_pattern.findall(response.text)

            logger.info(
                f"Page {current_page}: Found {len(page_product_urls)} URLs, "
                f"{len(titles)} titles, and {len(prices)} prices"
            )

            # Process products from the current page
            products_to_process = min(
                len(page_product_urls), len(titles), len(prices),
                max_items - len(all_products)
            )

            if products_to_process == 0:
                logger.warning(f"No products found on page {current_page}")
                break

            # Process each product from the current page
            for i in range(products_to_process):
                url = page_product_urls[i]

                # Clean up title (remove HTML entities)
                title = titles[i].strip()
                title = title.replace('&quot;', '"').replace('&amp;', '&')

                # Clean up price string and convert to float
                price_str = (
                    prices[i].strip().replace(' ', '').replace(',', '.')
                )
                try:
                    price = float(price_str)
                except ValueError:
                    price = None

                # Create a basic product object for reference
                basic_product = Product(
                    url=url,
                    title=title,
                    price_uah=price,
                    currency="UAH",
                    position=i + 1  # Add position to track order in search results
                )

                # Use ProductCrawler to get detailed product information
                product_crawler = ProductCrawler(client)
                detailed_product = await product_crawler.process_product_page(url)

                # If detailed extraction failed, use the basic product
                if not detailed_product:
                    logger.warning(f"Detailed extraction failed for {url}, using basic data")
                    product_data = basic_product.to_dict()
                else:
                    # Add position to the detailed product
                    detailed_product.position = i + 1
                    product_data = detailed_product.to_dict()
                    logger.info(
                        f"Detailed product: {detailed_product.title} | "
                        f"Regular: {detailed_product.regular_price_uah} | "
                        f"Discounted: {detailed_product.discounted_price_uah} | "
                        f"Image: {detailed_product.image_url} | "
                        f"Position: {detailed_product.position}"
                    )

                # Add to results and push to dataset
                all_products.append(product_data)
                await Actor.push_data(product_data)

                logger.info(f"Processed product: {title} - {price} UAH")

            # Check if we have enough products
            if len(all_products) >= max_items:
                logger.info(
                    f"Collected requested {max_items} products, "
                    f"stopping pagination"
                )
                break

            # If we found products on this page, continue to next page
            if products_to_process > 0:
                # Move to the next page
                current_page += 1

                # Add a delay between page requests to be polite
                await asyncio.sleep(random.uniform(1.0, 2.0))
            else:
                logger.info("No more products available")
                break

        logger.info(
            f"Pagination complete: processed {current_page} pages, "
            f"pushed {len(all_products)} products to the dataset"
        )

        return all_products

    except Exception as e:
        logger.error(f"Error during pagination: {str(e)}")
        return []


async def main() -> None:
    """
    Main entry point for the actor.

    This function:
    1. Reads the input
    2. Processes the search query
    3. Pushes product data to the dataset
    """
    # Initialize the Actor
    async with Actor:
        # Configure logging
        logger.remove()
        logger.add(sys.stderr, level="INFO")

        # Get input
        actor_input = await Actor.get_input() or {}

        # Validate input
        search_term = actor_input.get("search_term")
        max_items = actor_input.get("max_items", 10)

        if not search_term:
            raise ValueError("search_term is required")

        logger.info(f"Starting crawl for: '{search_term}', max items: {max_items}")

        # Set up HTTP client
        async with await setup_http_client() as client:
            # Use pagination to extract product data
            await paginate_search_results(client, search_term, max_items)


# Run the main function when the script is executed directly
if __name__ == "__main__":
    asyncio.run(main())
