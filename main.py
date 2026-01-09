from crawl4ai import AsyncWebCrawler
import asyncio


async def main():
    async with AsyncWebCrawler() as crawler:
        res = await crawler.arun("https://www.google.com")
        print(res)
if __name__ == '__main__':
    asyncio.run(main())