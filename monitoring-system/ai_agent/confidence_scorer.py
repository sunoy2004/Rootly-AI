from typing import Optional, List, Dict


class ConfidenceScorer:
    def score(
        self,
        anomaly_event: dict,
        cluster: Optional[dict],
        similar_incidents: List[dict],
    ) -> float:
        z_scores = [
            abs(anomaly_event.get("z_score", 0) or 0)
        ]
        anomalous = sum(1 for z in z_scores if z > 2)
        metric_agreement = min(anomalous / 4.0, 1.0)

        cluster_size = cluster.get("member_count", 0) if cluster else 0
        cluster_strength = min(cluster_size / 50.0, 1.0)

        if similar_incidents:
            memory_similarity = max(
                i.get("similarity", 0) for i in similar_incidents
            )
        else:
            memory_similarity = 0.0

        score = (
            0.4 * metric_agreement
            + 0.3 * cluster_strength
            + 0.3 * memory_similarity
        )
        return round(score, 2)
