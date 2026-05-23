from collections import defaultdict
from typing import List

import faiss
import numpy as np

from models import LogEntry, FailureCluster


class FailureClusterer:
    def cluster(
        self, entries: List[LogEntry], embeddings: np.ndarray
    ) -> List[FailureCluster]:
        n = len(entries)
        if n < 2:
            return []

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int):
            parent[find(a)] = find(b)

        k = min(50, n)
        scores_matrix, indices_matrix = index.search(embeddings, k)

        for i in range(n):
            for j_pos, j in enumerate(indices_matrix[i]):
                if j == i:
                    continue
                if scores_matrix[i][j_pos] > 0.85:
                    union(i, j)

        groups = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(i)

        clusters = []
        for root, members in groups.items():
            if len(members) < 2:
                continue

            member_embeddings = embeddings[members]
            centroid = member_embeddings.mean(axis=0)
            dists = np.dot(member_embeddings, centroid)
            rep_idx = members[np.argmax(dists)]

            cluster = FailureCluster(
                representative_message=entries[rep_idx].message,
                member_count=len(members),
                member_trace_ids=[entries[i].trace_id for i in members],
                affected_services=list(set(entries[i].service for i in members)),
                first_seen=min(entries[i].timestamp for i in members),
                last_seen=max(entries[i].timestamp for i in members),
            )
            clusters.append(cluster)

        return sorted(clusters, key=lambda c: c.member_count, reverse=True)
