"""Send a test Azure resource log event to Event Hubs using the Kafka protocol."""

import json
import os
import sys
from datetime import datetime, timezone


def main():
    try:
        from confluent_kafka import Producer
    except ImportError:
        print("Install confluent-kafka first:  pip install confluent-kafka")
        sys.exit(1)

    namespace = os.environ.get("EVENTHUB_NAMESPACE")
    conn_str = os.environ.get("EVENTHUB_CONNECTION_STRING")
    hub_name = os.environ.get("EVENTHUB_NAME", "logs")

    if not namespace or not conn_str:
        print("Set EVENTHUB_NAMESPACE and EVENTHUB_CONNECTION_STRING env vars")
        sys.exit(1)

    conf = {
        "bootstrap.servers": f"{namespace}:9093",
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "PLAIN",
        "sasl.username": "$ConnectionString",
        "sasl.password": conn_str,
    }

    event = {
        "records": [
            {
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "resourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                "operationName": "Microsoft.Compute/virtualMachines/write",
                "category": "Administrative",
                "resultType": "Success",
                "properties": {
                    "message": "Test log from ECF-ACA prototype",
                },
            }
        ]
    }

    producer = Producer(conf)

    def delivery_report(err, msg):
        if err:
            print(f"Delivery failed: {err}")
        else:
            print(f"Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

    payload = json.dumps(event).encode("utf-8")
    producer.produce(hub_name, value=payload, callback=delivery_report)
    producer.flush(timeout=10)
    print("Done.")


if __name__ == "__main__":
    main()
