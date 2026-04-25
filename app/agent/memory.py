from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from fastembed import TextEmbedding

from app.config import get_settings


class AgentMemory:
    """Qdrant-backed episodic memory per user (embedded mode — no server needed)."""

    _model: TextEmbedding | None = None
    _client: QdrantClient | None = None

    def __init__(self) -> None:
        self._settings = get_settings()

    @classmethod
    def _get_client(cls) -> QdrantClient:
        if cls._client is None:
            settings = get_settings()
            if settings.qdrant_path == ":memory:":
                cls._client = QdrantClient(":memory:")
                logger.info("Qdrant in-memory mode initialized")
            else:
                qdrant_path = Path(settings.qdrant_path).resolve()
                qdrant_path.mkdir(parents=True, exist_ok=True)
                cls._client = QdrantClient(path=str(qdrant_path))
                logger.info("Qdrant embedded mode initialized at {}", qdrant_path)
        return cls._client

    @classmethod
    async def _get_model(cls) -> TextEmbedding:
        if cls._model is None:

            def _load() -> TextEmbedding:
                return TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

            cls._model = await asyncio.to_thread(_load)
        return cls._model

    def _ensure_collection(self, vector_size: int) -> None:
        client = self._get_client()
        collections = client.get_collections()
        names = {c.name for c in collections.collections}
        if self._settings.qdrant_collection_name not in names:
            client.create_collection(
                collection_name=self._settings.qdrant_collection_name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
            )

    async def load(self, user_id: str, query: str) -> list[str]:
        model = await self._get_model()
        client = self._get_client()

        def _embed() -> list[float]:
            embeddings = list(model.embed([query]))
            v = embeddings[0]
            return v.tolist() if hasattr(v, "tolist") else list(v)

        vector = await asyncio.to_thread(_embed)
        await asyncio.to_thread(self._ensure_collection, len(vector))

        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id),
                )
            ]
        )

        def _search() -> list:
            return client.search(
                collection_name=self._settings.qdrant_collection_name,
                query_vector=vector,
                query_filter=filt,
                limit=5,
                with_payload=True,
            )

        results = await asyncio.to_thread(_search)
        texts: list[str] = []
        for hit in results:
            payload = hit.payload or {}
            prompt = str(payload.get("prompt", ""))
            result = str(payload.get("result", ""))
            texts.append(f"Past interaction:\nUser: {prompt}\nAssistant: {result}")
        return texts

    async def save(self, user_id: str, prompt: str, result: str) -> None:
        model = await self._get_model()
        client = self._get_client()

        def _embed() -> list[float]:
            embeddings = list(model.embed([prompt]))
            v = embeddings[0]
            return v.tolist() if hasattr(v, "tolist") else list(v)

        vector = await asyncio.to_thread(_embed)
        await asyncio.to_thread(self._ensure_collection, len(vector))

        point_id = hash((user_id, prompt, datetime.now(tz=UTC).isoformat())) & ((1 << 63) - 1)

        payload = {
            "user_id": user_id,
            "prompt": prompt,
            "result": result,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        def _upsert() -> None:
            client.upsert(
                collection_name=self._settings.qdrant_collection_name,
                points=[
                    qmodels.PointStruct(id=point_id, vector=vector, payload=payload),
                ],
            )

        await asyncio.to_thread(_upsert)

    async def list_recent(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return recent memory payloads for a user (best-effort ordering)."""
        client = self._get_client()
        await asyncio.to_thread(self._ensure_collection, 384)
        filt = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=user_id),
                )
            ]
        )

        def _scroll() -> list[dict]:
            entries: list[dict] = []
            offset = None
            while len(entries) < limit:
                scroll_res = client.scroll(
                    collection_name=self._settings.qdrant_collection_name,
                    scroll_filter=filt,
                    limit=min(64, limit - len(entries)),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                if isinstance(scroll_res, tuple):
                    points, next_offset = scroll_res
                else:
                    points = getattr(scroll_res, "points", []) or []
                    next_offset = getattr(scroll_res, "next_page_offset", None)

                for p in points:
                    pl = p.payload or {}
                    entries.append(pl)
                if next_offset is None:
                    break
                offset = next_offset
            return entries

        entries = await asyncio.to_thread(_scroll)

        def _ts(pl: dict) -> str:
            return str(pl.get("timestamp") or "")

        entries.sort(key=_ts, reverse=True)
        return entries[:limit]

    async def delete_all_for_user(self, user_id: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(self._ensure_collection, 384)

        def _delete() -> None:
            client.delete(
                collection_name=self._settings.qdrant_collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="user_id",
                                match=qmodels.MatchValue(value=user_id),
                            )
                        ]
                    )
                ),
            )

        await asyncio.to_thread(_delete)
        logger.info("Deleted Qdrant memory for user {}", user_id)
