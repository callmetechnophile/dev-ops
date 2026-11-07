import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self):
        self._client = None
        self._is_connected = False

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2.0)
            await self._client.ping()
            self._is_connected = True
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            self._is_connected = False
            self._client = None
            logger.warning(
                f"Could not connect to Redis at {settings.REDIS_URL}: {e}. Operating in resilient fallback mode."
            )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def publish_event(self, stream_key: str, event_data: Dict[str, Any]) -> Optional[str]:
        if not self._client or not self._is_connected:
            logger.warning(f"Redis unavailable, skipping stream dispatch to {stream_key}")
            return None
        try:
            return await self._client.xadd(stream_key, event_data)
        except Exception as e:
            logger.error(f"Failed to publish to Redis stream {stream_key}: {e}")
            return None


redis_manager = RedisManager()
