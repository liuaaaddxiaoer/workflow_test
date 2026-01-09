import os

from crawl4ai import AsyncWebCrawler
import asyncio
import aiofiles


async def redis():
    from redis.asyncio import Redis

    REDIS_URL="rediss://default:ASLRAAImcDFlZDM0YzQ3NTUxNTI0MjliYmVjNGFiYjBmZTExNzA2MXAxODkxMw@balanced-hagfish-8913.upstash.io:6379"
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    print(await redis.ping())
    print(await redis.get("name"))
    # 1. 确保 results 文件夹存在
    os.makedirs('results', exist_ok=True)

    # 2. 将文件保存到 results 文件夹下
    file_path = os.path.join('results', 'good.txt')
    file_path2 = os.path.join('results', 'good.html')
    # async with aiofiles.open(file_path, mode="w", encoding='utf-8') as f:
    #     await f.write(await redis.get('name'))
    #


async def main():
    async with AsyncWebCrawler() as crawler:
        os.makedirs('results', exist_ok=True)

        # 2. 将文件保存到 results 文件夹下
        file_path2 = os.path.join('results', 'good.html')
        res = await crawler.arun("https://jable.tv/hot/")
        async with aiofiles.open(file_path2, mode="w", encoding='utf-8') as f:
            await f.write(res.html)

if __name__ == '__main__':
    asyncio.run(main())