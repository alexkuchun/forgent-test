from __future__ import annotations
import os
import logging
import dramatiq
from dramatiq import Message
from dramatiq.brokers.redis import RedisBroker

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
_broker: RedisBroker | None = None

if REDIS_URL:
    _broker = RedisBroker(url=REDIS_URL)
    dramatiq.set_broker(_broker)
else:
    logger.warning("REDIS_URL not set; dramatiq queue disabled")


def broker_available() -> bool:
    return _broker is not None


def enqueue_process_tender(payload: dict):
    if not _broker:
        raise RuntimeError("Dramatiq broker is not configured; set REDIS_URL")
    message = Message(
        queue_name="default",
        actor_name="process_tender",
        args=(payload,),
        kwargs={},
        options={}
    )
    _broker.enqueue(message)
