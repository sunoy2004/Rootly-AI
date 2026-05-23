import logging
import os
from typing import List, Dict, Optional

import chromadb
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class IncidentMemory:
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "chromadb"),
            port=int(os.getenv("CHROMA_PORT", "8000")),
        )
        self.collection = self.client.get_or_create_collection(
            name="incident_memory",
            metadata={"hnsw:space": "cosine"},
        )
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def store(self, incident: dict):
        root_cause = incident.get("root_cause")
        if not root_cause:
            return

        text = (
            f"{incident['title']}. "
            f"Root cause: {root_cause}. "
            f"Resolution: {incident.get('resolution_notes', 'unknown')}"
        )

        embedding = self.model.encode(text).tolist()

        try:
            self.collection.add(
                ids=[incident["id"]],
                embeddings=[embedding],
                documents=[text],
                metadatas=[
                    {
                        "service": incident.get("affected_services", [""])[0],
                        "root_cause": root_cause,
                        "resolved_at": str(incident.get("resolved_at", "")),
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Memory store failed: {e}")

    def retrieve_similar(
        self, description: str, top_k: int = 3
    ) -> List[Dict]:
        try:
            embedding = self.model.encode(description).tolist()
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            similar = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                distance = results.get("distances", [[]])[0][i]
                if distance > 0.3:
                    continue
                similar.append(
                    {
                        "document": doc,
                        "metadata": results.get("metadatas", [[]])[0][i],
                        "similarity": 1 - distance,
                    }
                )
            return similar
        except Exception:
            return []
