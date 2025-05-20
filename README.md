# Prom.ua Scraper

An [Apify](https://apify.com) actor for scraping product data from [Prom.ua](https://prom.ua), Ukraine's leading e-commerce marketplace. This actor allows you to search for products and extract detailed information including prices, images, and more.

## Features

- Search for products on Prom.ua using keywords
- Extract comprehensive product details (title, prices, images)
- Support for price variations (regular and discounted prices)
- Pagination handling to collect products across multiple pages
- Proxy rotation and request optimization for reliable scraping
- Robust error handling and automatic retries
- Detailed logging for monitoring and debugging

## Input

The actor accepts the following input parameters:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `search_term` | String | Yes | | The keyword to search for on Prom.ua (e.g., "laptop", "жіночі сумки") |
| `max_items` | Integer | No | 10 | Maximum number of products to extract (1-1000) |
| `proxy` | Object | No | `{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}` | Proxy configuration for making requests |
| `maxConcurrency` | Integer | No | 10 | Maximum number of concurrent requests (1-50) |
| `requestTimeout` | Number | No | 30 | HTTP request timeout in seconds (5-120) |
| `maxRetries` | Integer | No | 5 | Maximum number of retries for failed requests (0-10) |
| `logLevel` | String | No | "INFO" | Level of logging detail (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

### Example Input

```json
{
  "search_term": "жіночі сумки",
  "max_items": 50,
  "proxy": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  },
  "maxConcurrency": 5,
  "requestTimeout": 30,
  "maxRetries": 3,
  "logLevel": "INFO"
}
```

## Output

The actor outputs product data to the default dataset. Each product includes the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `url` | String | URL of the product page |
| `title` | String | Product title/name |
| `regular_price_uah` | Number | Regular price in Ukrainian hryvnia (UAH) |
| `discounted_price_uah` | Number | Discounted price in UAH (if available) |
| `price_uah` | Number | Current price in UAH (for backward compatibility) |
| `currency` | String | Currency code (usually "UAH") |
| `image_url` | String | URL of the main product image |

### Example Output

```json
{
  "url": "https://prom.ua/ua/p1234567-noutbuk-apple-macbook.html",
  "title": "Ноутбук Apple MacBook Air 13\" M1 8/256GB 2020",
  "regular_price_uah": 42999,
  "discounted_price_uah": 39999,
  "price_uah": 39999,
  "currency": "UAH",
  "image_url": "https://images.prom.ua/3642517334_noutbuk-apple-macbook.jpg"
}
```

## Usage

### Running on Apify Platform

1. Visit the [Apify Console](https://console.apify.com)
2. Create a new task for the Prom.ua Scraper actor
3. Configure the input parameters according to your needs
4. Run the task and wait for it to finish
5. Download your data in JSON, CSV, or Excel format

### Running with Apify API

You can also run the actor programmatically using the Apify API:

```javascript
const Apify = require('apify');

Apify.main(async () => {
    const client = Apify.newClient({ token: 'YOUR_API_TOKEN' });

    // Start the actor
    const run = await client.actor('username/prom-ua-scraper').call({
        search_term: 'laptop',
        max_items: 50,
        proxy: {
            useApifyProxy: true,
            apifyProxyGroups: ['RESIDENTIAL']
        }
    });

    // Get the results
    const dataset = await client.dataset(run.defaultDatasetId).listItems();
    console.log('Results:', dataset.items);
});
```

### Running Locally

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your configuration (see `.env.example`)
4. Run the actor: `python -m src.main` or `apify run`

## Limitations

- The scraper respects Prom.ua's robots.txt and implements polite scraping practices
- Some product data may be unavailable if not provided by Prom.ua
- Anti-scraping measures may occasionally block requests, but the actor implements retry logic
- Very large result sets (>1000 products) may take significant time to process
- Product availability and pricing information may change frequently

## Additional Resources

- [Apify SDK Documentation](https://docs.apify.com/sdk/python)
- [Apify Platform Documentation](https://docs.apify.com/platform)
- [Prom.ua API Documentation](https://public-api.docs.prom.ua/) (for official API users)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Created and maintained by [YevheniiM](https://github.com/YevheniiM).
