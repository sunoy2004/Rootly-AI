import time
import sys
from elasticsearch import Elasticsearch, ConnectionError

ES_URL = "http://elasticsearch:9200"
TEMPLATE_NAME = "api-logs-template"
MAX_RETRIES = 10
RETRY_SLEEP = 5


def create_template(es: Elasticsearch) -> None:
    template_body = {
        "index_patterns": ["api-logs*"],
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "timestamp": {
                    "type": "date",
                    "format": "strict_date_optional_time",
                },
                "service": {"type": "keyword"},
                "level": {"type": "keyword"},
                "endpoint": {"type": "keyword"},
                "status_code": {"type": "integer"},
                "latency_ms": {"type": "float"},
                "message": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"},
                    },
                },
                "trace_id": {"type": "keyword"},
                "span_id": {"type": "keyword"},
                "environment": {"type": "keyword"},
            }
        },
    }

    es.indices.put_index_template(
        name=TEMPLATE_NAME,
        body={
            "index_patterns": template_body["index_patterns"],
            "template": {
                "settings": template_body["settings"],
                "mappings": template_body["mappings"],
            },
        },
    )
    print(f"Index template '{TEMPLATE_NAME}' created successfully.")


def main() -> None:
    es = Elasticsearch(ES_URL)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            health = es.cluster.health()
            print(f"Elasticsearch is ready (status: {health['status']})")
            create_template(es)
            return
        except ConnectionError as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: ES not ready yet ({exc})")
        except Exception as exc:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Unexpected error ({exc})")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SLEEP)

    print("Failed to connect to Elasticsearch after max retries.")
    sys.exit(1)


if __name__ == "__main__":
    main()
