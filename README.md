# Prom.ua Search Crawler

An [Apify](https://apify.com) actor for crawling search results from [Prom.ua](https://prom.ua) and extracting product information.

## Features

- Crawls search results from Prom.ua based on a search term
- Extracts product information including title, price, and currency
- Respects polite scraping practices with delays and proxy rotation
- Robust error handling and retry logic
- Comprehensive logging with loguru
- Full type hints with pydantic models
- Async implementation with httpx and asyncio
- Extensive test coverage

## Input

The actor accepts the following input parameters:

| Field | Type | Description |
|-------|------|-------------|
| `search_term` | String | The search term to use for finding products on Prom.ua |
| `max_items` | Integer | Maximum number of products to extract (default: 10) |

Example input:

```json
{
  "search_term": "жіночі сумки",
  "max_items": 20
}
```

## Output

The actor outputs product data to the default dataset in the following format:

```json
{
  "url": "https://prom.ua/ua/p12345-product-name.html",
  "title": "Product Name",
  "price_uah": 199.99,
  "currency": "UAH"
}
```

## Usage

### Running on Apify Platform

1. Visit the [Apify Console](https://console.apify.com)
2. Create a new task for the `promua_search_crawler` actor
3. Configure the input parameters
4. Run the task

### Running Locally

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the actor: `python -m src.main`

## Development

### Git Workflow

This project follows a structured Git workflow:

1. All development happens on the `develop` branch
2. Pull requests are created from `develop` to `master` for releases
3. CI/CD pipeline runs tests and linting on all pull requests
4. The `master` branch contains production-ready code

### Project Structure

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

### Running Tests

```bash
pytest
```

### Code Quality

This project uses:
- [Ruff](https://github.com/charliermarsh/ruff) for linting
- [Black](https://github.com/psf/black) for code formatting

To check code quality:

```bash
ruff check .
black --check .
```

To automatically fix issues:

```bash
ruff check --fix .
black .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
