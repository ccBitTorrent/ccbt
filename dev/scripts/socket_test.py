import asyncio
import logging
from pathlib import Path

from ccbt.discovery.tracker_udp_client import AsyncUDPTrackerClient

Path('logs').mkdir(exist_ok=True)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('logs/socket_test.log', encoding='utf-8')
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
logger.addHandler(handler)

async def main() -> None:
    client = AsyncUDPTrackerClient()
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()

if __name__ == '__main__':
    asyncio.run(main())
