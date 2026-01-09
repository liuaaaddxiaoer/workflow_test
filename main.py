from crawl4ai import AsyncWebCrawler
import asyncio
from redis.asyncio import *
REDIS_URL="rediss://default:ASLRAAImcDFlZDM0YzQ3NTUxNTI0MjliYmVjNGFiYjBmZTExNzA2MXAxODkxMw@balanced-hagfish-8913.upstash.io:6379"
redis = Redis.from_url(REDIS_URL, decode_responses=True)


async def main():
    async with AsyncWebCrawler() as crawler:
        print(await redis.ping())
        print(await redis.get("name"))
        res = await crawler.arun("https://www.google.com")
        print(res)
if __name__ == '__main__':
    asyncio.run(main())