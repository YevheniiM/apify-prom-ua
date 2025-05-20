# Prom.ua Scraper - Developer Documentation

This document provides detailed technical information for developers working with the Prom.ua Scraper actor.

## Project Structure

- `src/` - Source code
  - `main.py` - Entry point, sets up the actor and orchestrates the crawling process
  - `config.py` - Configuration settings (headers, delays, proxy settings)
  - `utils/` - Utility functions
    - `http.py` - HTTP utilities with retry logic and error handling
  - `crawlers/` - Crawler implementations
    - `search_crawler.py` - Handles crawling search result pages
    - `product_crawler.py` - Handles extracting data from product pages
  - `models/` - Data models
    - `product.py` - Pydantic model for product data
  - `data/` - Static data files
    - `categories.json` - Category information for Prom.ua
- `tests/` - Test suite
  - `test_search_url.py` - Tests for search URL building
  - `test_product_parse.py` - Tests for product data extraction
- `INPUT_SCHEMA.json` - Apify input schema definition
- `README.md` - User-facing documentation
- `DOCUMENTATION.md` - Developer documentation (this file)

## Architecture

The actor follows a modular architecture with clear separation of concerns:

1. **Input Handling**: The `main.py` file reads and validates input parameters from the Apify platform.
2. **HTTP Client Setup**: A configured HTTPX client is created with proper headers, timeouts, and proxy settings.
3. **Search Pagination**: The `paginate_search_results` function handles iterating through search result pages.
4. **Product Extraction**: The `ProductCrawler` class extracts detailed product information from product pages.
5. **Data Storage**: Extracted data is pushed to the Apify dataset using the Apify SDK.

## Input Schema

The actor uses the Apify Input Schema v1 specification. The schema is defined in `INPUT_SCHEMA.json` and includes:

```json
{
  "title": "Prom.ua Scraper Input",
  "description": "Input schema for the Prom.ua product scraper",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "search_term": {
      "title": "Search Term",
      "type": "string",
      "description": "The keyword to search for on Prom.ua",
      "editor": "textfield"
    },
    "max_items": {
      "title": "Maximum Items",
      "type": "integer",
      "description": "Maximum number of products to extract",
      "editor": "number",
      "default": 10
    },
    // Additional properties...
  },
  "required": ["search_term"]
}
```

## Data Model

The `Product` model in `src/models/product.py` defines the structure of extracted product data:

```python
class Product(BaseModel):
    url: str = Field(..., description="Product page URL")
    title: Optional[str] = Field(None, description="Product title/name")
    regular_price_uah: Optional[float] = Field(None, description="Regular price in UAH")
    discounted_price_uah: Optional[float] = Field(None, description="Discounted price in UAH, if available")
    price_uah: Optional[float] = Field(None, description="Current price in UAH (for backward compatibility)")
    currency: Optional[str] = Field(None, description="Currency code (usually UAH)")
    image_url: Optional[str] = Field(None, description="URL of the main product image")
```

## Extraction Techniques

The actor uses several techniques to extract product data:

1. **JSON-LD Extraction**: The primary method is to extract structured data from JSON-LD scripts in the product pages.
2. **HTML Parsing**: When JSON-LD is not available, the actor falls back to HTML parsing using regular expressions and BeautifulSoup.
3. **Pattern Matching**: Multiple patterns are tried for each data point to handle variations in the page structure.

## Error Handling

The actor implements robust error handling:

1. **Request Retries**: Failed requests are automatically retried with exponential backoff.
2. **Empty Response Detection**: The actor can detect and handle empty or blocked responses.
3. **Parsing Fallbacks**: If one extraction method fails, alternative methods are attempted.
4. **Comprehensive Logging**: Detailed logs help diagnose issues during execution.

## Development Workflow

This project follows a structured Git workflow:

1. All development happens on the `develop` branch
2. Pull requests are created from `develop` to `master` for releases
3. CI/CD pipeline runs tests and linting on all pull requests
4. The `master` branch contains production-ready code

## Testing

The project includes a comprehensive test suite:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_product_parse.py

# Run with coverage
pytest --cov=src
```

## Code Quality

This project uses:
- [Ruff](https://github.com/charliermarsh/ruff) for linting
- [Black](https://github.com/psf/black) for code formatting
- [MyPy](https://mypy.readthedocs.io/) for type checking

To check code quality:

```bash
ruff check .
black --check .
mypy src
```

## Deployment

To deploy the actor to the Apify platform:

1. Make sure you have the Apify CLI installed: `npm install -g apify-cli`
2. Log in to your Apify account: `apify login`
3. Build and deploy the actor: `apify push`

## Performance Considerations

- The actor uses asynchronous HTTP requests for better performance
- Concurrency is controlled to avoid overloading the target site
- Request delays are implemented to respect the site's resources
- Proxy rotation helps avoid IP-based rate limiting

## Troubleshooting

Common issues and solutions:

1. **Empty Results**: Check if the search term is valid and returns products on Prom.ua
2. **Blocked Requests**: Try using a different proxy group or increasing request delays
3. **Missing Data**: Some products may not have all fields available on Prom.ua
4. **Timeout Errors**: Increase the `requestTimeout` parameter for slow connections

## Future Improvements

Potential enhancements for future versions:

1. Add support for category-based browsing
2. Implement product review extraction
3. Add seller information extraction
4. Support for product variants/options
5. Implement advanced filtering options
