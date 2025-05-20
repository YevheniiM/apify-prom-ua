# 📝 Augment Guidelines for the **Prom.ua Scraper Project**

## 1 · Mind-set & Workflow

| Step | Expectation |
|------|-------------|
| **Design-note first** | Before emitting code, write a brief rationale: goals, inputs, outputs, key selectors, edge-cases. |
| **Think hard / iterate** | Run (or mentally simulate) the code: imports, async, network, JSON parse, dataset push. If something could break, iterate until fixed. |
| **Real data** | Always hit real Prom.ua pages (or stored HTML fixtures for unit tests). No placeholder URLs or fake responses in production code. |
| **No shortcuts** | Don’t omit retries, logging, or type hints “for brevity.” Deliver production-ready code every time. |

---

## 2 · Project Structure (never collapse to one file)

src/
main.py                 # actor entry, input parsing, queue bootstrap
config.py               # constants: headers, delays, proxy config
utils/                  # generic helpers
http.py             # async fetch + tenacity retry
crawlers/               # page-type specific logic
search_crawler.py   # processes search pages
category_crawler.py # (if added) processes category pages
product_crawler.py  # parses product pages
models/
product.py          # pydantic models
seller.py
tests/                    # pytest units with real HTML fixtures
data/                     # static assets (e.g. categories.json)
Dockerfile
requirements.txt
.github/workflows/python-ci.yml

*All new code must fit this layout or expand it sensibly.*

---

## 3 · Coding Standards

* **Language & Runtime**  Python 3.11+   `apify` SDK ≥ 2.5  
* **Async everywhere**  Use `httpx[http2]` + `async def`.
* **Type safety**  Full type annotations; models via `pydantic`.
* **Logging**  `loguru`  
  - INFO = high-level flow  - DEBUG = selector details / raw HTML snippet  
* **Retries**  Wrap network calls with `tenacity` (`wait_random_exponential`, `stop_after_attempt(4)`).
* **Anti-bot**  SessionPool, random mobile/desktop UAs, Apify Residential proxy, 200-600 ms jitter after each request.
* **Max-items guard**  Stop crawling promptly once the requested limit is reached.
* **Error handling**  If selectors fail → log 400 chars of HTML, retire session, retry once; raise descriptive exception if still failing.

---

## 4 · Testing & CI

* Each parser must have at least **one pytest** using a stored HTML fixture.  
* A nightly **smoke schedule** (10 URLs) must run in Apify to catch breakage.  
* CI (`python-ci.yml`):  
  1. `setup-python`   2. `pip install -r requirements.txt`  
  3. `ruff . --fix --exit-zero`   4. `black --check .`  
  5. `pytest -q`

---

## 5 · Deliverable Rules for Augment

1. **One answer → multiple files** wrapped as  
   \```filename.ext  
   # code …  
   \```  
   Never return a monolithic file.  
2. **Self-check** before final output: code compiles, pytest passes, lint clean.  
3. **Clarify > guess** – if requirements are ambiguous, ask for details.

---

## 6 · Compliance & Ethics

* Scrape **only publicly available data**; no login or private endpoints.  
* Respect Prom.ua server load.  
* Do not collect personal data beyond what is shown on public product/seller pages.

---

### ✨ Follow these guidelines for every future contribution to keep the project stable, maintainable, and production-ready.