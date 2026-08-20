from pathlib import Path


class SmartCraneSourceCatalog:
    """Discovers integration contracts from local Smart Crane source without executing it."""
    EXPECTED = {
        "cloud_iot_listener": "cloud-backend/ac-backend-iot-hub-listener/ac_backend_iot_hub_listener/handlers/telemetry.py",
        "edge_deployment": "edge-modules/src/deployment.template.json",
        "edge_pipeline": "edge-modules/azure-pipelines.yml",
        "telemetry_model": "core/smart_crane_core/models.py",
        "cassandra_telemetry": "core/smart_crane_core/cassandra/crane_telemetry.py",
        "event_model": "cloud-frontend/ac-frontend-rest-api/ac_frontend_rest_api/api/events/models.py",
    }

    def __init__(self, root: str):
        self.root = Path(root)

    def status(self) -> dict:
        contracts = {name: {"present": (self.root / rel).is_file(), "path": rel}
                     for name, rel in self.EXPECTED.items()}
        return {"connected": self.root.is_dir(), "root": str(self.root), "contracts": contracts,
                "evidence_mapping": {
                    "config": ["crane_uuid", "version", "published status"],
                    "notification": ["event_uuid", "crane_uuid", "event_actions", "created_date"],
                    "motion_fault": ["motion_uuid", "fault_code", "created_date"],
                    "telemetry": ["motion_uuid", "edge_uuid", "query_timestamp", "motion_data", "vfd_status"],
                    "motion_data": ["current", "drive_alarm", "drive_fault", "drive_fault_list", "loadcell",
                                    "torque", "speed_in_hz", "limit_switch"],
                }}
