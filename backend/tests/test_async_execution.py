import asyncio
import time

async def long_running(timeout=3):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        await asyncio.sleep(1)
    return True

async def quick_task(flag):
    await asyncio.sleep(0.5)
    flag.append(True)

def test_async_sleep_allows_concurrency():
    async def runner():
        flag = []
        long_task = asyncio.create_task(long_running(2))
        start = time.monotonic()
        await quick_task(flag)
        elapsed = time.monotonic() - start
        await long_task
        assert elapsed < 1.5
        assert flag == [True]
    asyncio.run(runner())

