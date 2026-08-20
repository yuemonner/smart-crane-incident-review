from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, SecretStr

from .models import EvidenceEvent, EvidenceMode, EvidenceType, IntegrityStatus


class CloudLogin(BaseModel):
    email: str
    password: SecretStr


class SmartCraneCloudReadOnlyConnector:
    """Smart Crane cloud client with an explicit GET-only operational allowlist."""

    ALLOWED = ("/auth/status/", "/dashboard/", "/cranes/", "/customers/",
               "/sites/", "/locations/", "/crane-systems/")

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    @property
    def connected(self):
        return bool(self._access_token)

    async def login(self, credentials: CloudLogin):
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            response = await client.post("/auth/login/", json={
                "email": credentials.email,
                "password": credentials.password.get_secret_value(),
            })
            response.raise_for_status()
            tokens = response.json()
            self._access_token = tokens["access_token"]
            self._refresh_token = tokens.get("refresh_token")
            user = await self._get("/auth/status/")
        return {"connected": True, "user": user.get("username") or user.get("email"),
                "scope": "GET-only Smart Crane investigation allowlist", "credentials_stored": False}

    def disconnect(self):
        self._access_token = self._refresh_token = None

    async def _get(self, path: str, params: dict | None = None):
        if not self.connected:
            raise RuntimeError("Smart Crane Cloud is not connected")
        if not (path in self.ALLOWED or
                (path.startswith("/cranes/") and any(path.endswith(s) for s in
                 ("/config/", "/params/", "/status/", "/versions/", "/hc/")))):
            raise ValueError("Path is outside the read-only allowlist")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20,
                                     headers={"Authorization": f"Bearer {self._access_token}"}) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def status(self):
        if not self.connected:
            return {"configured": True, "connected": False, "credentials_stored": False}
        user = await self._get("/auth/status/")
        return {"configured": True, "connected": True,
                "user": user.get("username") or user.get("email"),
                "credentials_stored": False, "mode": "GET-only"}

    async def collect(self):
        cranes = await self._get("/cranes/")
        customers = await self._get("/customers/")
        sites = await self._get("/sites/")
        cranes = cranes.get("results", cranes.get("value", [])) if isinstance(cranes, dict) else cranes
        customers = customers.get("results", customers.get("value", [])) if isinstance(customers, dict) else customers
        sites = sites.get("results", sites.get("value", [])) if isinstance(sites, dict) else sites
        customer_by_id = {str(x.get("id")): x.get("name") or x.get("customer_name") for x in customers}
        site_by_id = {str(x.get("id")): x for x in sites}
        retrieved_at = datetime.now(timezone.utc)
        events: list[EvidenceEvent] = []
        assets: list[dict[str, Any]] = []
        for crane in cranes:
            crane_id = crane["id"]
            entity = crane.get("crane_uuid") or crane.get("device_id") or str(crane_id)
            versions = await self._get(f"/cranes/{crane_id}/versions/", {"limit": 10})
            latest = versions[0] if versions else {}
            occurred = latest.get("created_at") or crane.get("updated_date") or crane.get("created_date")
            if occurred:
                events.append(EvidenceEvent(
                    id=f"Smart Crane-cloud-config-{crane_id}-{latest.get('version', crane.get('version'))}",
                    type=EvidenceType.config_change, occurred_at=occurred, entity_id=entity,
                    title=f"Configuration version {latest.get('version', crane.get('version', 'unknown'))}",
                    source="Smart Crane Cloud REST API · crane versions",
                    source_url=f"{self.base_url}/cranes/{crane_id}/versions/",
                    retrieved_at=retrieved_at, evidence_mode=EvidenceMode.live,
                    integrity=IntegrityStatus(transport="HTTPS",
                        limitation="Normalized from a live REST response; API response was not cryptographically signed or independently archived."),
                    attributes={"crane_id": crane_id, "crane_name": crane.get("crane_name"),
                                "config_profile": str(latest.get("version") or crane.get("version") or ""),
                                "status": latest.get("status", crane.get("status")),
                                "notes": latest.get("notes"),
                                "customer": customer_by_id.get(str(crane.get("customer") or crane.get("customer_id"))),
                                "site": (site_by_id.get(str(crane.get("site") or crane.get("site_id"))) or {}).get("name"),
                                "provenance": "live Smart Crane Cloud GET response"}))
            asset = {k: crane.get(k) for k in
                           ("id", "device_id", "crane_uuid", "crane_name", "job_number",
                            "serial_number", "crane_capacity", "capacity_unit", "active", "version", "status")}
            asset["customer_name"] = customer_by_id.get(str(crane.get("customer") or crane.get("customer_id")))
            asset["site_name"] = (site_by_id.get(str(crane.get("site") or crane.get("site_id"))) or {}).get("name")
            assets.append(asset)
        return {"cranes": assets, "customers": customers, "sites": sites, "events": events,
                "retrieved_at": retrieved_at}
