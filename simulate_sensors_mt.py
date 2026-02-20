#!/usr/bin/env python3
"""
Enterprise Multi-Tenant MQTT Sensor Simulator

Fetches real tenant/site/asset/sensor hierarchy from PostgreSQL,
lets the user pick which tenants to simulate, then publishes
telemetry to:
    {tenant_code}/{site_code}/sensors/{sensor_code}

Payload matches mqtt-ingestion's simple-sensor handler.
"""

import os
import sys
import json
import time
import random
from datetime import datetime

import paho.mqtt.client as mqtt

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 is required.  Install with:  pip install psycopg2-binary")
    sys.exit(1)

# =============================
# CONFIGURATION
# =============================

MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

# PostgreSQL — parse the async URL or fall back to defaults
_pg_url = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5431/aastreli",
)
# Strip SQLAlchemy driver prefix so psycopg2 can use it
PG_DSN = _pg_url.replace("postgresql+asyncpg://", "postgresql://")

# =============================
# FETCH TENANT HIERARCHY FROM PG
# =============================

HIERARCHY_SQL = """
SELECT
    t.tenant_code,
    si.site_code,
    a.asset_code,
    s.sensor_code
FROM sensors s
JOIN tenants t  ON t.id = s.tenant_id
JOIN assets  a  ON a.id = s.asset_id
JOIN sites   si ON si.id = a.site_id
WHERE s.is_active  = true  AND s.is_deleted = false
  AND a.is_active  = true  AND a.is_deleted = false
  AND si.is_active = true  AND si.is_deleted = false
  AND t.is_active  = true  AND t.is_deleted = false
ORDER BY t.tenant_code, si.site_code, a.asset_code, s.sensor_code
"""


def fetch_hierarchy():
    """Return {tenant_code: [{site_code, asset_code, sensor_code}, ...]}."""
    conn = psycopg2.connect(PG_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(HIERARCHY_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    tenants: dict = {}
    for row in rows:
        tc = row["tenant_code"]
        tenants.setdefault(tc, []).append(
            {
                "site_code": row["site_code"],
                "asset_code": row["asset_code"],
                "sensor_code": row["sensor_code"],
            }
        )
    return tenants


# =============================
# TENANT SELECTION
# =============================


def select_tenants(tenants: dict) -> list[str]:
    """Interactive CLI prompt — returns list of chosen tenant codes."""
    codes = sorted(tenants.keys())
    print("\nAvailable tenants:")
    for i, code in enumerate(codes, 1):
        sensor_count = len(tenants[code])
        print(f"  {i}. {code}  ({sensor_count} sensors)")

    print(f"\nEnter tenant numbers (comma-separated) or 'all':  ", end="")
    choice = input().strip().lower()

    if choice == "all":
        return codes

    selected = []
    for part in choice.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(codes):
                selected.append(codes[idx])
            else:
                print(f"  Warning: index {part} out of range, skipping")
        else:
            # Allow typing tenant_code directly
            if part in codes:
                selected.append(part)
            else:
                print(f"  Warning: '{part}' not found, skipping")

    if not selected:
        print("No tenants selected. Exiting.")
        sys.exit(0)

    return selected


# =============================
# SENSOR DATA GENERATOR
# =============================


def generate_sensor_payload(sensor_code: str) -> dict:
    base_temp = 65.0
    base_vibration = 2.5
    base_pressure = 100.0
    base_humidity = 45.0

    temp_var = random.uniform(-10, 5)
    vib_var = random.uniform(-0.5, 0.5)
    press_var = random.uniform(-10, 10)
    humid_var = random.uniform(-5, 5)

    # 10% anomaly chance
    is_anomaly = random.random() < 0.1
    if is_anomaly:
        temp_var += random.uniform(15, 25)
        vib_var += random.uniform(3, 5)

    payload = {
        "sensor_id": sensor_code,
        "temperature": round(base_temp + temp_var, 2),
        "vibration": round(base_vibration + vib_var, 2),
        "pressure": round(base_pressure + press_var, 2),
        "humidity": round(base_humidity + humid_var, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }
    return payload, is_anomaly


# =============================
# MQTT CALLBACKS
# =============================


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"Connection failed with code {rc}")


# =============================
# MAIN
# =============================


def main():
    print("=" * 60)
    print("  Enterprise Multi-Tenant MQTT Simulator")
    print("=" * 60)

    # 1. Fetch hierarchy from PostgreSQL
    print(f"\nConnecting to PostgreSQL: {PG_DSN.split('@')[1] if '@' in PG_DSN else PG_DSN}")
    try:
        tenants = fetch_hierarchy()
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    if not tenants:
        print("No active tenants/sensors found in database.")
        sys.exit(1)

    total_sensors = sum(len(v) for v in tenants.values())
    print(f"Found {len(tenants)} tenant(s), {total_sensors} sensor(s) total.")

    # 2. Let user pick tenants
    selected_codes = select_tenants(tenants)

    # Build flat list of (tenant_code, site_code, sensor_code) to publish
    targets = []
    for tc in selected_codes:
        for entry in tenants[tc]:
            targets.append((tc, entry["site_code"], entry["sensor_code"]))

    print(f"\nSimulating {len(targets)} sensor(s) across {len(selected_codes)} tenant(s)")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Interval: {PUBLISH_INTERVAL}s")
    print(f"Topic format: {{tenant_code}}/{{site_code}}/sensors/{{sensor_code}}")
    print("=" * 60)

    # 3. Connect to MQTT
    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    # 4. Publish loop
    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")

            for tenant_code, site_code, sensor_code in targets:
                topic = f"{tenant_code}/{site_code}/sensors/{sensor_code}"
                payload, is_anomaly = generate_sensor_payload(sensor_code)

                result = client.publish(topic, json.dumps(payload))
                marker = " !! ANOMALY" if is_anomaly else ""
                if result.rc == 0:
                    print(
                        f"  [{topic}] "
                        f"T={payload['temperature']}C "
                        f"V={payload['vibration']}Hz"
                        f"{marker}"
                    )
                else:
                    print(f"  FAIL [{topic}]")

            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopping simulator...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
