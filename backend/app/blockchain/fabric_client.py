"""Pluggable immutable ledger backends."""
from __future__ import annotations
import logging
from typing import Any, Protocol
from ..config import Settings, get_settings
from ..models.database import BlockchainRecord
from ..utils.helpers import sha256_of, utcnow

logger = logging.getLogger("fmn.blockchain")
GENESIS_HASH = "0" * 64

class LedgerUnavailable(RuntimeError):
    pass

class LedgerBackend(Protocol):
    def append(self, db: Any, event_type: str, payload: dict) -> str: ...
    def verify(self, db: Any, tx_hash: str) -> dict: ...
    def verify_chain(self, db: Any) -> dict: ...

class LocalHashChainLedger:
    name = "local-hashchain"

    def append(self, db: Any, event_type: str, payload: dict) -> str:
        last = db.query(BlockchainRecord).order_by(BlockchainRecord.block_number.desc()).first()
        prev = last.tx_hash if last else GENESIS_HASH
        number = (last.block_number + 1) if last else 1
        ts = utcnow()
        tx_hash = sha256_of({"prev": prev, "event_type": event_type, "payload": payload, "timestamp": ts.isoformat()})
        db.add(BlockchainRecord(block_number=number, tx_hash=tx_hash, prev_hash=prev, event_type=event_type, payload=payload, timestamp=ts))
        db.commit()
        return tx_hash

    def verify(self, db: Any, tx_hash: str) -> dict:
        rec = db.query(BlockchainRecord).filter_by(tx_hash=tx_hash).first()
        if not rec:
            return {"valid": False, "reason": "not_found"}
        expected = sha256_of({"prev": rec.prev_hash, "event_type": rec.event_type, "payload": rec.payload, "timestamp": rec.timestamp.isoformat()})
        return {"valid": expected == rec.tx_hash, "tx_hash": tx_hash, "block_number": rec.block_number}

    def verify_chain(self, db: Any) -> dict:
        rows = db.query(BlockchainRecord).order_by(BlockchainRecord.block_number.asc()).all()
        prev = GENESIS_HASH
        for i, row in enumerate(rows):
            recomputed = sha256_of({"prev": row.prev_hash, "event_type": row.event_type, "payload": row.payload, "timestamp": row.timestamp.isoformat()})
            if row.prev_hash != prev or recomputed != row.tx_hash:
                return {"valid": False, "broken_at_block": row.block_number, "checked": i + 1}
            prev = row.tx_hash
        return {"valid": True, "checked": len(rows)}

class FabricLedger:
    name = "hyperledger-fabric"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        try:
            import fabric_sdk_py  # noqa: F401
        except ImportError as exc:
            raise LedgerUnavailable("fabric-sdk-py not installed") from exc

    def append(self, db: Any, event_type: str, payload: dict) -> str:
        raise LedgerUnavailable("Fabric gateway not configured; falling back to local ledger")

    def verify(self, db: Any, tx_hash: str) -> dict:
        raise LedgerUnavailable("Fabric verify unavailable")

    def verify_chain(self, db: Any) -> dict:
        raise LedgerUnavailable("Fabric verify_chain unavailable")

class EthereumLedger:
    name = "ethereum"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if not settings.ethereum_rpc_url:
            raise LedgerUnavailable("ETHEREUM_RPC_URL not configured")
        try:
            from web3 import Web3  # noqa: F401
        except ImportError as exc:
            raise LedgerUnavailable("web3 not installed") from exc

    def append(self, db: Any, event_type: str, payload: dict) -> str:
        raise LedgerUnavailable("Ethereum append not implemented; falling back to local")

    def verify(self, db: Any, tx_hash: str) -> dict:
        raise LedgerUnavailable("Ethereum verify unavailable")

    def verify_chain(self, db: Any) -> dict:
        raise LedgerUnavailable("Ethereum verify_chain unavailable")

class ResilientLedger:
    def __init__(self, primary: Any, fallback: LocalHashChainLedger, settings: Settings) -> None:
        self.primary = primary
        self.fallback = fallback
        self.mode = settings.blockchain_mode
        self.degraded = primary is fallback

    def append(self, db: Any, event_type: str, payload: dict) -> str:
        if self.primary is self.fallback:
            return self.fallback.append(db, event_type, payload)
        try:
            return self.primary.append(db, event_type, payload)
        except Exception as exc:
            logger.warning("Primary ledger failed (%s); using local fallback", exc)
            self.degraded = True
            return self.fallback.append(db, event_type, payload)

    def verify(self, db: Any, tx_hash: str) -> dict:
        return self.fallback.verify(db, tx_hash)

    def verify_chain(self, db: Any) -> dict:
        return self.fallback.verify_chain(db)

def get_ledger(settings: Settings | None = None) -> ResilientLedger:
    settings = settings or get_settings()
    fallback = LocalHashChainLedger()
    primary = fallback
    mode = settings.blockchain_mode.lower()
    try:
        if mode == "fabric":
            primary = FabricLedger(settings)
        elif mode == "ethereum" and settings.ethereum_rpc_url:
            primary = EthereumLedger(settings)
    except LedgerUnavailable as exc:
        logger.warning("Blockchain backend unavailable (%s); using local hash-chain", exc)
    return ResilientLedger(primary, fallback, settings)
