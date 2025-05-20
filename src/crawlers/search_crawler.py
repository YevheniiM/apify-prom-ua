"""
Search crawler for Prom.ua.

This module handles crawling search result pages and extracting product links.
"""

import re
import asyncio
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urljoin

import httpx
from loguru import logger
from apify import Actor, Request

from src.config import PRODUCT_URL_REGEX, MAX_PAGES
from src.utils.http import fetch_html, build_search_url


class SearchCrawler:
    """
    Crawler for Prom.ua search results pages.

    This class handles crawling search result pages and extracting product links.
    """

    def __init__(self, client: httpx.AsyncClient, session_id: Optional[str] = None):
        """
        Initialize the search crawler.

        Args:
            client: HTTPX client for making requests
            session_id: Optional session ID for logging
        """
        self.client = client
        self.session_id = session_id
        self.product_url_pattern = re.compile(PRODUCT_URL_REGEX)

    async def extract_product_urls(self, html: str, base_url: str) -> List[str]:
        """
        Extract product URLs from search results HTML.

        Args:
            html: The HTML content of the search results page
            base_url: The base URL for resolving relative URLs

        Returns:
            List of absolute product URLs
        """
        # Save the HTML to a file for debugging if needed
        # with open("search_page.html", "w") as f:
        #     f.write(html)

        # Use a more specific regex to find product URLs
        # This pattern matches href="/ua/p{numbers}-{text}.html"
        product_pattern = re.compile(r'href="(/ua/p\d+-[^"]+\.html)"')
        matches = product_pattern.finditer(html)

        # Extract and normalize URLs
        urls = []
        for match in matches:
            relative_url = match.group(1)
            # Skip URLs that contain "product-opinions" as they're not product pages
            if "product-opinions" in relative_url:
                continue
            absolute_url = urljoin(base_url, relative_url)
            urls.append(absolute_url)

        # Log the number of URLs found
        logger.info(f"Found {len(urls)} product URLs on page")

        # If no URLs were found, try a different approach
        if not urls:
            logger.warning("No product URLs found with primary pattern, trying alternative pattern")
            # Try a more lenient pattern
            alt_pattern = re.compile(r'href="(/ua/p[^"]+)"')
            matches = alt_pattern.finditer(html)

            for match in matches:
                relative_url = match.group(1)
                # Skip URLs that contain "product-opinions" as they're not product pages
                if "product-opinions" in relative_url:
                    continue
                absolute_url = urljoin(base_url, relative_url)
                urls.append(absolute_url)

            logger.info(f"Found {len(urls)} product URLs with alternative pattern")

        # Return unique URLs
        return list(dict.fromkeys(urls))

    async def has_next_page(self, html: str) -> bool:
        """
        Check if there is a next page of search results.

        Args:
            html: The HTML content of the current search results page

        Returns:
            True if there is a next page, False otherwise
        """
        # Look for pagination links with rel="next"
        next_page_pattern = re.compile(r'<a[^>]+rel="next"[^>]*>')
        return bool(next_page_pattern.search(html))

    async def crawl_search_pages(
        self, search_term: str, max_items: int
    ) -> List[str]:
        """
        Crawl search result pages and collect product URLs.

        Args:
            search_term: The search query
            max_items: Maximum number of product URLs to collect

        Returns:
            List of product URLs
        """
        collected_urls: Set[str] = set()
        page = 1

        while len(collected_urls) < max_items and page <= MAX_PAGES:
            # Build the search URL for the current page
            url = build_search_url(search_term, page)

            # Fetch the search results page
            try:
                html = await fetch_html(self.client, url, self.session_id)

                # Extract product URLs from the page
                page_urls = await self.extract_product_urls(html, url)

                # Add new URLs to the collection
                for product_url in page_urls:
                    if len(collected_urls) < max_items:
                        collected_urls.add(product_url)
                    else:
                        break

                # Log progress
                logger.info(
                    f"Page {page}: Found {len(page_urls)} products, "
                    f"collected {len(collected_urls)}/{max_items} total"
                )

                # Check if there are more pages
                has_next = await self.has_next_page(html)
                if not has_next or not page_urls:
                    logger.info("No more pages or no products found on current page")
                    break

                # Move to the next page
                page += 1

            except Exception as e:
                logger.error(f"Error crawling search page {page}: {str(e)}")
                if page > 1:
                    # If we've already processed at least one page, continue with what we have
                    break
                else:
                    # If we couldn't process even the first page, re-raise the exception
                    raise

        # Check if we found any products
        if not collected_urls:
            logger.warning(f"No product URLs found for search term: {search_term}")
            # Return empty list instead of raising an exception
            return []

        # Convert set to list for consistent ordering
        return list(collected_urls)

    async def enqueue_product_urls(
        self,
        search_term: str,
        max_items: int,
        request_queue: Any,
    ) -> int:
        """
        Crawl search pages and enqueue product URLs to the request queue.

        Args:
            search_term: The search query
            max_items: Maximum number of product URLs to collect
            request_queue: Apify RequestQueue for enqueueing URLs

        Returns:
            Number of URLs enqueued
        """
        # Collect product URLs from search pages
        product_urls = await self.crawl_search_pages(search_term, max_items)

        # Enqueue each product URL to the request queue
        enqueued_count = 0
        for url in product_urls:
            # Create a Request object using the from_url method
            request = Request.from_url(
                url=url,
                user_data={"label": "PRODUCT"}
            )
            await request_queue.add_request(request)
            enqueued_count += 1

        logger.info(
            f"Enqueued {enqueued_count} product URLs to the request queue"
        )
        return enqueued_count
