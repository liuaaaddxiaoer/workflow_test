
import asyncio
import re
import os
from lxml import html
from redis.asyncio import Redis
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, MemoryAdaptiveDispatcher, RateLimiter, \
    GeolocationConfig
from playwright.async_api import Page

IS_DOCKER = True

REDIS_URL = "rediss://default:ASLRAAImcDFlZDM0YzQ3NTUxNTI0MjliYmVjNGFiYjBmZTExNzA2MXAxODkxMw@balanced-hagfish-8913.upstash.io:6379"
redis = Redis.from_url(REDIS_URL, decode_responses=True)

async def main():
    # --- 1. 种子初始化 (仅需执行一次) ---
    # 检查队列，如果没任务了，由第一个启动的容器负责“补货”
    if await redis.llen('task_queue_list') == 0:
        print("Initializing task queue...")
        initial_urls = [f'https://jable.tv/hot/{i}/' for i in range(1, 1469)]
        await redis.rpush('task_queue_list', *initial_urls)

    # --- 2. 浏览器 Hook 与拦截配置 (保持你原有逻辑) ---
    async def _abort(route, request):
        if any(x in request.url for x in [".jpg", ".png", ".mp4", ".woff2"]):
            await route.abort()
        else:
            await route.continue_()

    async def _on_page_context_created(page: Page, **kwargs):
        await page.route('**/*', _abort)

    # Docker 建议使用 headless=True
    browser_cfg = BrowserConfig(
        headless=True if IS_DOCKER else False,
        enable_stealth=True,
        extra_args=["--disable-blink-features=AutomationControlled", "--no-sandbox","--start-maximized", "--disable-dev-shm-usage"]
    )

    run_cfg = CrawlerRunConfig(
        user_agent_mode='random',
        magic=True,
        stream=True,
        page_timeout=15000,
        locale='en-US',
        timezone_id='Asia/Singapore',
        mean_delay=1.2,
        max_range=0.5,
        geolocation=GeolocationConfig(latitude=1.364917, longitude=103.8198)
    )

    # 保持你原有的 Dispatcher 配置
    rate1 = RateLimiter(base_delay=(2, 5))
    dipatcher = MemoryAdaptiveDispatcher(rate_limiter=rate1)
    dipatcher.max_session_permit = 4

    rate2 = RateLimiter(base_delay=(2, 4))
    dipatcher2 = MemoryAdaptiveDispatcher(rate_limiter=rate2)
    dipatcher2.max_session_permit = 8

    # --- 3. 核心执行逻辑 ---
    async with AsyncWebCrawler(config=browser_cfg) as f:
        f.crawler_strategy.set_hook('on_page_context_created', _on_page_context_created)

        while True:
            # 分布式领取任务：每个容器拿走 1 个列表页
            current_list_url = await redis.lpop('task_queue_list')
            if not current_list_url:
                print("🏁 所有任务已处理完毕，容器退出。")
                break

            print(f"🚀 正在爬取列表页: {current_list_url}")

            try:
                # 爬取列表页 (使用原有 wait_for)
                res_gen = await f.arun_many(
                    [current_list_url],
                    config=run_cfg.clone(wait_for=".video-img-box.mb-e-20"),
                    dispatcher=dipatcher
                )

                async for result in res_gen:
                    if not result.html: continue

                    doc = html.fromstring(result.html)
                    detail_links = doc.xpath(
                        '//div[@class="video-img-box mb-e-20"]/div[@class="img-box cover-md"]/a/@href')

                    if not detail_links: continue

                    # --- 高效去重：只保留没爬过的 ---
                    todo_items = []
                    for link in detail_links:
                        if not await redis.hexists('finish_m3u8_urls', link):
                            todo_items.append(link)

                    if not todo_items: continue

                    # 爬取详情页提取 m3u8
                    item_res_gen = await f.arun_many(
                        todo_items,
                        config=run_cfg.clone(wait_for=".count"),
                        dispatcher=dipatcher2
                    )

                    async for item_result in item_res_gen:
                        if not item_result.html: continue

                        M3U8_PATTERN = re.compile(r"hlsUrl\s*=\s*['\"](https?://[^'\"]+?\.m3u8[^'\"]*?)['\"]")
                        match = M3U8_PATTERN.search(item_result.html)

                        if match:
                            m3u8_url = match.group(1)
                            # 存入 Redis Set (用于去重) 和 Hash (用于记录详情)
                            # sismember 在这里可以双重保险
                            if not await redis.sismember('m3u8_urls', m3u8_url):
                                await redis.sadd('m3u8_urls', m3u8_url)
                                await redis.hset('finish_m3u8_urls', item_result.url, m3u8_url)
                                print(f"✅ 成功: {item_result.url} -> {m3u8_url}")
                        else:
                            # 记录未找到的，避免重复尝试
                            await redis.sadd('no_m3u8_urls', item_result.url)

            except Exception as e:
                print(f"🔥 运行出错 {current_list_url}: {e}")
                # 出错了可以把任务塞回队列末尾重试
                await redis.rpush('task_queue_list', current_list_url)


if __name__ == "__main__":
    asyncio.run(main())