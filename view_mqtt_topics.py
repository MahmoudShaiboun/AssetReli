#!/usr/bin/env python3
"""Subscribe to all MQTT topics and display messages as they arrive."""

import paho.mqtt.client as mqtt
import json
from datetime import datetime

BROKER = "localhost"
PORT = 1883
TOPIC = "#"  # wildcard: all topics

seen_topics = set()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(TOPIC)
        print(f"Connected to {BROKER}:{PORT}  |  Subscribed to: {TOPIC}")
        print("Waiting for messages (Ctrl+C to stop)...\n")
    else:
        print(f"Connection failed (code {reason_code})")


def on_message(client, userdata, msg):
    topic = msg.topic
    is_new = topic not in seen_topics
    if is_new:
        seen_topics.add(topic)

    try:
        payload = json.loads(msg.payload.decode())
        sensor = payload.get("sensor_id", "")
        temp = payload.get("temperature", "")
        vib = payload.get("vibration", "")
        label = "NEW " if is_new else "    "
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{label}[{ts}] {topic:<28} sensor={sensor:<16} temp={temp}  vib={vib}")
    except Exception:
        print(f"    [{topic}] {msg.payload.decode()[:120]}")


def main():
    print("MQTT Topic Viewer")
    print("=" * 60)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n\nTopics seen ({len(seen_topics)}):")
        for t in sorted(seen_topics):
            print(f"  {t}")
        client.disconnect()


if __name__ == "__main__":
    main()
