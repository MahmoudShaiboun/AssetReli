from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedTopic:
    """Result of parsing an MQTT topic."""

    sensor_code: str
    raw_topic: str
    # Future: tenant_code, site_code will be added in Phase 3B
    tenant_code: Optional[str] = None
    site_code: Optional[str] = None


def parse_topic(topic: str) -> Optional[ParsedTopic]:
    """
    Parse an MQTT topic to extract sensor identifiers.

    Currently handles:
        sensors/{sensor_id}    -> sensor_code = sensor_id
        equipment/{sensor_id}  -> sensor_code = sensor_id

    Future (Phase 3B):
        {tenant_code}/{site_code}/sensors/{sensor_code}

    Returns None if the topic cannot be parsed.
    """
    parts = topic.split("/")

    if len(parts) == 2 and parts[0] in ("sensors", "equipment"):
        return ParsedTopic(sensor_code=parts[1], raw_topic=topic)

    # Future: {tenant}/{site}/sensors/{sensor}
    if len(parts) == 4 and parts[2] == "sensors":
        return ParsedTopic(
            sensor_code=parts[3],
            raw_topic=topic,
            tenant_code=parts[0],
            site_code=parts[1],
        )

    return None
