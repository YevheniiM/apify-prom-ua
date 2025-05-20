"""
Main entry point for the Prom.ua search crawler Apify actor.

This module is the entry point for the actor when run with "apify run".
"""

import asyncio
from src.main import main

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
