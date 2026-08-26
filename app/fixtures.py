from datetime import datetime, timedelta, timezone

from .models import EvidenceEvent, EvidenceType

INCIDENT_TIME = datetime(2026, 8, 14, 16, 32, tzinfo=timezone.utc)


def _event(id: str, type: EvidenceType, hours: float, entity: str | None, title: str,
           source: str, attrs: dict, url: str | None = None) -> EvidenceEvent:
    return EvidenceEvent(id=id, type=type, occurred_at=INCIDENT_TIME + timedelta(hours=hours),
                         entity_id=entity, title=title, source=source,
                         source_url=url or f"https://demo.smart-crane.local/evidence/{id}", attributes=attrs)


def demo_events() -> list[EvidenceEvent]:
    crane_context = {"site": "Site A", "zone": "Bay 3 / Hoist zone", "control_panel": "Panel H-07"}
    events = [
        _event("LKG-07-REV217", EvidenceType.test, -60, "Crane-07",
               "Last known good validation completed", "Commissioning test record",
               {"last_known_good": True, "software_revision": "app 0.35", "firmware": "0.35",
                "config_profile": "C16", "runtime_state": "module healthy; uploads normal; no repeated reconnect attempts",
                "successful_test_cycles": 3, "validated_by": "Engineering", **crane_context}),
        _event("ADO-COMMIT-a3f8e21", EvidenceType.commit, -50, None,
               "Adjust module reconnect handling", "Azure DevOps",
               {"commit": "a3f8e21", "repository": "smart-crane"}),
        _event("ADO-BUILD-1842", EvidenceType.build, -47, None, "Build 1842 succeeded",
               "Azure Pipelines", {"build": 1842, "commit": "a3f8e21", "result": "succeeded"}),
        _event("ADO-TEST-1842", EvidenceType.test, -46, None, "Connectivity smoke tests passed",
               "Azure Test Plans", {"passed": 128, "failed": 0, "gap": "No customer-site firewall check"}),
        _event("DEPLOY-4.9-C17", EvidenceType.deployment, -36, "Crane-07",
               "Application 0.36 deployed", "Deployment manifest",
               {"firmware": "0.36", "previous_firmware": "0.35", "config_profile": "C17", "build": 1842,
                "deployed_at": "2026-08-13 04:32 UTC", **crane_context}),
        _event("CFG-07-C17", EvidenceType.config_change, -35.5, "Crane-07",
               "Device profile C17 activated", "Config audit",
               {"config_profile": "C17", "previous": "C16", "activated_at": "2026-08-13 05:02 UTC", **crane_context}),
        _event("IOT-07-LAT-1", EvidenceType.device_event, -3, "Crane-07",
               "Repeated reconnect attempts", "IoT Hub",
               {"pattern": "module_health_unhealthy_after_reconnect", "value_ms": 1880, "load_pct": 84,
                "observed_at": "2026-08-14 13:32 UTC", **crane_context}),
        _event("IOT-07-LAT-2", EvidenceType.device_event, -0.05, "Crane-07",
               "Module stopped uploading", "IoT Hub",
               {"pattern": "module_upload_missing", "load_pct": 87, "latency_ms": 2210,
                "observed_at": "2026-08-14 16:29 UTC", **crane_context}),
        _event("EDGE-07-HIRES", EvidenceType.device_event, -0.01, "Crane-07",
               "High-resolution machine-state window captured", "Edge capture",
               {"capture_window": "16:29-16:32 UTC", "duration_sec": 180, "sample_rate_hz": 50,
                "signals": "machine state, module state, connection state, controller signals", "load_pct": 87, **crane_context}),
        _event("ALARM-07-ESTOP", EvidenceType.alarm, 0, "Crane-07",
               "Module unhealthy; connectivity under review", "IoT Hub",
               {"alarm": "MODULE_UNHEALTHY", "load_pct": 87, "module_healthy": False,
                "uploading": False, "trigger_time": "2026-08-14 16:32 UTC", **crane_context}),
    ]

    # Seven comparable peers share the same application / profile exposure; three show matching module-health signals.
    for i in range(1, 8):
        crane = f"Crane-{i + 7:02d}"
        customer = ["Site group A", "Site group B", "Site group C"][i % 3]
        events.append(_event(f"INV-{crane}", EvidenceType.deployment, -30 - i / 10, crane,
                             "Fleet deployment inventory", "Deployment manifest",
                             {"firmware": "0.36", "config_profile": "C17", "customer": customer}))
        if i <= 3:
            events.append(_event(f"PRE-{crane}", EvidenceType.device_event, -i / 3, crane,
                                 "Repeated reconnect attempts", "IoT Hub",
                                 {"pattern": "module_health_unhealthy_after_reconnect",
                                  "value_ms": 1700 + i * 31, "load_pct": 76 + i,
                                  "customer": customer}))

    for i in range(35, 43):
        crane = f"Crane-{i:02d}"
        events.append(_event(f"INV-{crane}", EvidenceType.deployment, -20, crane,
                             "Fleet deployment inventory", "Deployment manifest",
                             {"firmware": "0.35", "config_profile": "C16", "customer": "Other"}))
    return events
