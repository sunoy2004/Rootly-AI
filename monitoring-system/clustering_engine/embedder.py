import hashlib
from typing import List

import aioredis
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    def __init__(self, redis_url: str):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.redis_url = redis_url
        self.redis = None

    async def init(self):
        self.redis = await aioredis.from_url(self.redis_url)

    def _cache_key(self, text: str) -> str:
        return "emb:" + hashlib.sha256(text.encode()).hexdigest()

    async def embed_batch(self, texts: List[str]) -> np.ndarray:
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = await self.redis.get(key)
            if cached:
                results[i] = np.frombuffer(cached, dtype=np.float32)
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            embeddings = self.model.encode(
                uncached_texts,
                normalize_embeddings=True,
                batch_size=32,
            )
            for idx, embedding in zip(uncached_indices, embeddings):
                text_idx = uncached_indices.index(idx)
                await self.redis.setex(
                    self._cache_key(uncached_texts[text_idx]),
                    7200,
                    embedding.astype(np.float32).tobytes(),
                )
                results[idx] = embedding

        return np.array(results, dtype=np.float32)
