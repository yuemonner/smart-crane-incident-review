from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .fixtures import INCIDENT_TIME, demo_events
from .ado import AzureDevOpsReadOnlyConnector
from .aceco import AcecoSourceCatalog
from .models import (CaptureClass, CriticalSnapshot, EvidenceEvent, EvidenceMode,
                     IncidentRecord, IncidentRequest, IncidentSummary, Investigation,
                     WhereElseResult)
from .service import EvidenceService
from .settings import settings
from .local_evidence import LocalAcecoEvidenceConnector
from .postgres import AcecoPostgresReadOnlyConnector
from .aceco_cloud import AcecoCloudReadOnlyConnector, CloudLogin
from .memory import IncidentMemory
from .cosmos import CosmosTelemetryReadOnlyConnector
from .ledger import EvidenceLedger
from .capture import RuntimeCapture, TraceSample
from .reconstruction import demo_reconstruction_report

app = FastAPI(title="ACECO Smart Crane Incident API", version="0.1.0",
              description="Read-only cyber-physical incident reconstruction and fleet exposure analysis")
service = EvidenceService(demo_events())
catalog = AcecoSourceCatalog(settings.aceco_source_root)
local_evidence = LocalAcecoEvidenceConnector(settings.aceco_notes_root)
postgres = AcecoPostgresReadOnlyConnector(
    settings.aceco_postgres_host, settings.aceco_postgres_port,
    settings.aceco_postgres_database, settings.aceco_postgres_user,
    settings.aceco_postgres_password)
cloud = AcecoCloudReadOnlyConnector(settings.aceco_cloud_api_url)
memory = IncidentMemory(settings.incident_memory_path)
ledger = EvidenceLedger(settings.evidence_ledger_path)
runtime_capture = RuntimeCapture()
cosmos = CosmosTelemetryReadOnlyConnector(settings.aceco_cosmos_host, settings.aceco_cosmos_port,
    settings.aceco_cosmos_username, settings.aceco_cosmos_password, settings.aceco_cosmos_keyspace)
fleet_identity: dict = {"cranes": [], "customers": [], "sites": [], "retrieved_at": None}
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def add_events(incoming: list[EvidenceEvent]):
    existing = {event.id for event in service.events}
    added = [event for event in incoming if event.id not in existing]
    service.events.extend(added)
    ledger_entries = [ledger.append(event) for event in added if event.evidence_mode != EvidenceMode.demo]
    return added, ledger_entries


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "demo" if settings.aceco_demo_mode else "live",
            "evidence_events": len(service.events), "ado_configured": bool(settings.ado_pat),
            "aceco_sources": catalog.status()["connected"]}


@app.get("/api/sources")
async def sources():
    ado = {"configured": bool(settings.ado_pat), "connected": False,
           "organization": settings.ado_org, "project": settings.ado_project}
    if settings.ado_pat:
        try:
            ado.update(await AzureDevOpsReadOnlyConnector(
                settings.ado_org, settings.ado_project, settings.ado_pat).status())
        except Exception as exc:
            ado["error"] = f"{type(exc).__name__}: connection unavailable"
    try:
        postgres_status = postgres.status()
    except Exception as exc:
        postgres_status = {"configured": postgres.configured, "connected": False,
                           "error": f"{type(exc).__name__}: connection unavailable"}
    try:
        cloud_status = await cloud.status()
    except Exception as exc:
        cloud_status = {"configured": True, "connected": False,
                        "error": f"{type(exc).__name__}: session unavailable"}
    try:
        cosmos_status = cosmos.status()
    except Exception as exc:
        cosmos_status = {"configured": cosmos.configured, "connected": False,
                         "error": f"{type(exc).__name__}: connection unavailable"}
    return {"azure_devops": ado, "aceco_code": catalog.status(), "local_evidence": local_evidence.status(),
            "aceco_postgres": postgres_status,
            "aceco_cloud": cloud_status,
            "fleet_telemetry": cosmos_status}


@app.post("/api/sources/ado/refresh")
async def refresh_ado():
    if not settings.ado_pat:
        raise HTTPException(503, "ADO_PAT is not configured")
    connector = AzureDevOpsReadOnlyConnector(settings.ado_org, settings.ado_project, settings.ado_pat)
    try:
        incoming = await connector.collect()
    except Exception as exc:
        raise HTTPException(502, f"Azure DevOps read failed: {type(exc).__name__}") from exc
    added, _ = add_events(incoming)
    return {"fetched": len(incoming), "added": len(added), "total_evidence": len(service.events)}


@app.post("/api/sources/local/refresh")
def refresh_local():
    incoming = local_evidence.collect()
    added, _ = add_events(incoming)
    return {"fetched": len(incoming), "added": len(added), "total_evidence": len(service.events),
            "source": "local ACECO notes and bounded logs"}


@app.post("/api/sources/postgres/refresh")
def refresh_postgres():
    if not postgres.configured:
        raise HTTPException(503, "ACECO PostgreSQL is not configured")
    try:
        incoming = postgres.collect()
    except Exception as exc:
        raise HTTPException(502, f"ACECO PostgreSQL read failed: {type(exc).__name__}") from exc
    added, _ = add_events(incoming)
    return {"fetched": len(incoming), "added": len(added), "total_evidence": len(service.events),
            "source": "live read-only ACECO PostgreSQL", "tables": ["faults", "notifications"]}


@app.post("/api/sources/cosmos/refresh")
def refresh_cosmos(request: IncidentRequest):
    if not cosmos.configured:
        raise HTTPException(503, "ACECO Cosmos Cassandra is not configured")
    try:
        incoming = cosmos.collect(request.entity_id, request.incident_time, request.window_hours)
    except Exception as exc:
        raise HTTPException(502, f"Cosmos telemetry read failed: {type(exc).__name__}") from exc
    added, _ = add_events(incoming)
    return {"fetched": len(incoming), "added": len(added), "total_evidence": len(service.events),
            "source": "live read-only ACECO Cosmos Cassandra", "table": "cloud_core.crane_telemetry"}


@app.post("/api/sources/aceco-cloud/login")
async def login_aceco_cloud(credentials: CloudLogin):
    try:
        return await cloud.login(credentials)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(401, "ACECO Cloud login failed") from exc


@app.post("/api/sources/aceco-cloud/refresh")
async def refresh_aceco_cloud():
    global fleet_identity
    if not cloud.connected:
        raise HTTPException(401, "Connect ACECO Cloud first")
    try:
        result = await cloud.collect()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "ACECO Cloud read failed") from exc
    added, _ = add_events(result["events"])
    fleet_identity = {key: result.get(key, []) for key in ("cranes", "customers", "sites")}
    fleet_identity["retrieved_at"] = result.get("retrieved_at")
    return {"cranes": result["cranes"], "fetched": len(result["events"]), "added": len(added),
            "customers": len(result.get("customers", [])), "sites": len(result.get("sites", [])),
            "total_evidence": len(service.events), "mode": "live GET-only"}


@app.post("/api/sources/aceco-cloud/disconnect")
def disconnect_aceco_cloud():
    cloud.disconnect()
    return {"connected": False}


@app.get("/api/demo")
def demo():
    investigation = service.investigate(IncidentRequest(entity_id="Crane-07", incident_time=INCIDENT_TIME,
                                                         evidence_mode=EvidenceMode.demo))
    return {"investigation": investigation, "where_else": service.where_else(investigation)}


@app.get("/api/reconstruction/demo")
def reconstruction_demo():
    return demo_reconstruction_report()


@app.get("/api/incidents", response_model=list[IncidentSummary])
def incidents(mode: EvidenceMode | None = None):
    return service.incidents(mode)


@app.get("/api/fleet/identity")
def fleet_identities():
    return fleet_identity


@app.get("/api/memory/incidents", response_model=list[IncidentRecord])
def remembered_incidents():
    return memory.list()


@app.get("/api/memory/incidents/{incident_id}", response_model=IncidentRecord)
def remembered_incident(incident_id: str):
    record = memory.get(incident_id)
    if not record:
        raise HTTPException(404, "Incident record not found")
    return record


@app.put("/api/memory/incidents/{incident_id}", response_model=IncidentRecord)
def remember_incident(incident_id: str, record: IncidentRecord):
    if incident_id != record.id:
        raise HTTPException(400, "Incident ID mismatch")
    return memory.put(record)


@app.post("/api/evidence", response_model=EvidenceEvent, status_code=201)
def ingest(event: EvidenceEvent):
    if any(e.id == event.id for e in service.events):
        raise HTTPException(409, "Evidence ID already exists")
    service.events.append(event)
    if event.evidence_mode != EvidenceMode.demo:
        ledger.append(event)
    return event


@app.get("/api/ledger/status")
def ledger_status():
    return ledger.status()


@app.get("/api/capture/status")
def capture_status():
    return {**runtime_capture.status(), "ledger": ledger.status()}


@app.post("/api/capture/trace")
def capture_trace(sample: TraceSample):
    return runtime_capture.trace(sample)


@app.post("/api/capture/critical-snapshot", response_model=EvidenceEvent, status_code=201)
def capture_critical_snapshot(snapshot: CriticalSnapshot):
    event = runtime_capture.critical(snapshot)
    if any(existing.id == event.id for existing in service.events):
        raise HTTPException(409, "Snapshot evidence ID already exists")
    service.events.append(event)
    ledger.append(event)
    return event


@app.post("/api/capture/audit-event", response_model=EvidenceEvent, status_code=201)
def capture_audit_event(event: EvidenceEvent):
    if event.capture_class != CaptureClass.audit_event:
        raise HTTPException(400, "Manual intervention/configuration records must use capture_class=audit_event")
    if any(existing.id == event.id for existing in service.events):
        raise HTTPException(409, "Evidence ID already exists")
    service.events.append(event)
    ledger.append(event)
    return event


@app.post("/api/incidents/investigate", response_model=Investigation)
def investigate(request: IncidentRequest):
    return service.investigate(request)


@app.post("/api/incidents/where-else", response_model=WhereElseResult)
def where_else(request: IncidentRequest):
    return service.where_else(service.investigate(request))
