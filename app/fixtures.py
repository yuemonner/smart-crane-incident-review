from datetime import datetime, timedelta, timezone

from .models import EvidenceEvent, EvidenceType

INCIDENT_TIME = datetime(2026, 8, 14, 14, 32, tzinfo=timezone.utc)


def _event(id: str, type: EvidenceType, hours: float, entity: str | None, title: str,
           source: str, attrs: dict, url: str | None = None) -> EvidenceEvent:
    return EvidenceEvent(id=id, type=type, occurred_at=INCIDENT_TIME + timedelta(hours=hours),
                         entity_id=entity, title=title, source=source,
                         source_url=url or f"https://demo.smart-crane.local/evidence/{id}", attributes=attrs)


def demo_events() -> list[EvidenceEvent]:
    events = [
        _event("LKG-07-REV217", EvidenceType.test, -60, "Crane-07",
               "Last known good validation completed", "Commissioning test record",
               {"last_known_good": True, "software_revision": "rev 217", "firmware": "4.8",
                "config_profile": "C16", "runtime_state": "3 successful operating cycles; no Redis exception storm",
                "successful_test_cycles": 3, "validated_by": "Engineering"}),
        _event("ADO-COMMIT-a3f8e21", EvidenceType.commit, -50, None,
               "Harden E-stop notification retry handling", "Azure DevOps",
               {"commit": "a3f8e21", "repository": "smart-crane"}),
        _event("ADO-BUILD-1842", EvidenceType.build, -47, None, "Build 1842 succeeded",
               "Azure Pipelines", {"build": 1842, "commit": "a3f8e21", "result": "succeeded"}),
        _event("ADO-TEST-1842", EvidenceType.test, -46, None, "Notification tests passed",
               "Azure Test Plans", {"passed": 128, "failed": 0, "gap": "No high-load latency test"}),
        _event("DEPLOY-4.9-C17", EvidenceType.deployment, -36, "Crane-07",
               "Firmware 4.9 deployed", "Deployment manifest",
               {"firmware": "4.9", "previous_firmware": "4.8", "config_profile": "C17", "build": 1842}),
        _event("CFG-07-C17", EvidenceType.config_change, -35.5, "Crane-07",
               "Configuration profile C17 activated", "Config audit",
               {"config_profile": "C17", "previous": "C16"}),
        _event("IOT-07-LAT-1", EvidenceType.device_event, -4, "Crane-07",
               "Elevated notification persistence latency", "IoT Hub",
               {"pattern": "notification_persistence_latency", "value_ms": 1880, "load_pct": 84}),
        _event("IOT-07-LAT-2", EvidenceType.device_event, -0.05, "Crane-07",
               "Notification acknowledgement missing", "IoT Hub",
               {"pattern": "notification_ack_missing", "load_pct": 87}),
        _event("ALARM-07-ESTOP", EvidenceType.alarm, 0, "Crane-07",
               "E-stop activated during hoisting", "IoT Hub",
               {"alarm": "E_STOP", "load_pct": 87, "notification_delivered": False}),
    ]

    # Exactly 27 peers share firmware/config exposure; exactly 11 show precursor signals.
    for i in range(1, 28):
        crane = f"Crane-{i + 7:02d}"
        customer = ["North Harbor", "Baltic Lift", "Ardent Marine"][i % 3]
        events.append(_event(f"INV-{crane}", EvidenceType.deployment, -30 - i / 10, crane,
                             "Fleet deployment inventory", "Deployment manifest",
                             {"firmware": "4.9", "config_profile": "C17", "customer": customer}))
        if i <= 11:
            events.append(_event(f"PRE-{crane}", EvidenceType.device_event, -i / 3, crane,
                                 "Elevated notification persistence latency", "IoT Hub",
                                 {"pattern": "notification_persistence_latency",
                                  "value_ms": 1700 + i * 31, "load_pct": 76 + i,
                                  "customer": customer}))

    for i in range(35, 43):
        crane = f"Crane-{i:02d}"
        events.append(_event(f"INV-{crane}", EvidenceType.deployment, -20, crane,
                             "Fleet deployment inventory", "Deployment manifest",
                             {"firmware": "4.8", "config_profile": "C16", "customer": "Other"}))
    return events
