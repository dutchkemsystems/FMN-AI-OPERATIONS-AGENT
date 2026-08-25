"""Optional MongoDB document sink for unstructured audit logs."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("fmn.mongo")

_client: Any = None
_checked = False


def _get_client() -> Any:
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    from ..config import get_settings

    url = get_settings().mongo_url
    if not url:
        return None
    try:
        import pymongo

        _client = pymongo.MongoClient(url, serverSelectionTimeoutMS=2000)
        _client.server_info()
        logger.info("Connected to MongoDB at %s", url)
    except Exception:
        logger.warning("MongoDB unavailable; Mongo sink disabled")
        _client = None
    return _client


def log_document(collection: str, doc: dict) -> bool:
    """Insert a document into a MongoDB collection. Returns True on success."""
    client = _get_client()
    if client is None:
        return False
    try:
        db = client.get_default_database() or client["fmn"]
        db[collection].insert_one(dict(doc))
        return True
    except Exception:
        logger.debug("MongoDB write to %s skipped", collection)
        return False
