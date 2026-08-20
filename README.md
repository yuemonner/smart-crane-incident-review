# ACECO Smart Crane Incident Review

This is a read-only internal investigation tool for ACECO/Norlink Smart Crane incidents. It turns one incident into a fleet-wide **WHERE ELSE?** assessment while clearly separating confirmed evidence, unestablished claims, and evidence gaps.

The validated operating model is:

1. Reconstruct the machine episode and its physical state.
2. Establish the last known good software/configuration/runtime/test state when explicit evidence exists.
3. Identify what changed.
4. Compare device-specific evidence with peer devices and deployment cohorts.
5. Support a human test / rollback / redeploy / hold decision.
6. Preserve the decision and observed outcome for the next investigation.

The application does not assume machines fail frequently. It addresses the high cost of reconstructing context when an unusual event or risky production change does require investigation.

## Architecture boundary

This application is a **system of context**, not a replacement system of record:

- Continuous high-volume telemetry remains in the telemetry platform.
- A bounded operational trace holds only the recent context that may be difficult to reconstruct later.
- A critical trigger freezes an episode snapshot containing version/configuration, operating mode, critical state, state diff, recent actions, related IDs, and intervention context.
- Manual interventions and configuration changes can be appended as explicit audit events.
- A local evidence ledger preserves normalized non-demo evidence in an append-only table with a verifiable hash chain.
- Source systems continue to own deployment, telemetry, ticket, and maintenance truth.

Every normalized record distinguishes `observed`, `inferred`, and `human_asserted` evidence. Inferred records may carry confidence. A later record can supersede an earlier record without deleting it.

The ledger detects application-level mutation; it is not hardware-backed immutability and does not establish source integrity, clock accuracy, sensor calibration, or legal chain of custody.

When a human decision is recorded, the application also freezes the observed facts, supported assessment, assumptions, unknowns, and evidence IDs available at that time. Later evidence can change the current conclusion without rewriting that historical decision context.

## Run the instant demo

Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8010
```

Open http://127.0.0.1:8010. API documentation is at http://127.0.0.1:8010/docs.

The built-in scenario requires no credentials and is explicitly demo evidence. For real evidence, configure ADO and call `POST /api/sources/ado/refresh`. `GET /api/sources` reports each connector separately and never silently describes a disconnected source as live.

## Tests

```powershell
pytest -q
```

## Optional Azure DevOps read access

Copy `.env.example` to `.env` and set `ADO_ORG`, `ADO_PROJECT`, and `ADO_PAT`. Use a least-privilege PAT with read scopes only. The connector reads repositories, commits, pull requests, builds, and build-linked work items; it does not create or change ADO resources. Work-item ownership, state, and target date become incident coordination fields when linked evidence falls inside the investigation window. `.env` is gitignored.

The normalized `EvidenceEvent` model supports commits, pull requests, builds, deployments, tests, configuration changes, device events, and alarms. `POST /api/evidence` is local application ingestion only—it does not write back to any source or device. There is no device-control path in the application.

## Optional live ACECO PostgreSQL evidence

Create an SSH tunnel to the edge host, then set the `ACECO_POSTGRES_*` values shown in `.env.example`. Use only a dedicated account with `SELECT` grants and `default_transaction_read_only=on`.

The connector independently forces every database session into read-only mode. It runs fixed, bounded queries against only `faults` and `notifications`; it explicitly excludes `edge_users` and exposes no arbitrary SQL facility. Check the connection with `GET /api/sources`, then ingest normalized evidence with `POST /api/sources/postgres/refresh`.

## Optional live Cosmos physical telemetry

Set the `ACECO_COSMOS_*` values in `.env` using a dedicated read-only Cassandra identity. `POST /api/sources/cosmos/refresh` runs one bounded `SELECT` against `cloud_core.crane_telemetry` for a selected edge UUID and time window. It normalizes physical fields such as drive alarms/faults, load, current, torque, output frequency, temperature, and drive-ready state. No generic CQL endpoint and no write operation exist.

Browser access to Azure Portal is not treated as an application credential. Until the Cassandra connection succeeds, the UI says telemetry is offline. Per-row hashes document the retrieved normalized content, but do **not** prove source immutability, clock accuracy, sensor calibration, or legal chain of custody.

## Evidence modes and memory

Demo, cached, partial, and live records are separate workspaces. Queries never silently combine them. The incident selector is generated from alarm records in the selected mode. Source retrieval timestamps and integrity limitations are shown beside evidence.

Human-recorded owner, checkpoint, and explicit decision fields are stored in `work/incident_memory.sqlite3`. This is local application memory only; it never writes to ACECO Cloud, ADO, databases, or devices.

## Core endpoints

- `POST /api/incidents/investigate` reconstructs a bounded evidence timeline and WHAT CHANGED context.
- `POST /api/incidents/where-else` derives a traceable exposure signature and ranks peer assets.
- `GET /api/incidents?mode=live` lists real selectable alarm incidents for one evidence mode.
- `GET /api/fleet/identity` returns the last live REST identity mapping for cranes, customers, and sites.
- `PUT /api/memory/incidents/{id}` saves a local human decision record.
- `GET /api/demo` returns the complete zero-configuration demo.
- `GET /api/health` reports local service status.
- `GET /api/sources` reports ADO, ACECO source-contract, and fleet-telemetry connection truthfully.
- `POST /api/sources/ado/refresh` ingests current ADO evidence into the normalized evidence store.
- `POST /api/sources/local/refresh` ingests timestamped ACECO engineering/log evidence while excluding connection notes and secret-bearing lines.
- `POST /api/sources/postgres/refresh` ingests bounded live ACECO fault and notification evidence using an enforced read-only session.
- `POST /api/sources/cosmos/refresh` ingests bounded live physical telemetry for one crane and time window.
- `POST /api/capture/trace` adds a lightweight sample to the bounded operational ring buffer.
- `POST /api/capture/critical-snapshot` freezes a critical machine episode and appends it to the evidence ledger.
- `POST /api/capture/audit-event` appends an explicit manual intervention/configuration audit event.
- `GET /api/capture/status` reports buffer ownership, capacity, and ledger verification status.
- `GET /api/ledger/status` verifies the local evidence hash chain and states its integrity limitations.

Example request body:

```json
{"entity_id":"Crane-07","incident_time":"2026-08-14T14:32:00Z","window_hours":72,"evidence_mode":"demo"}
```

## Validation still required

Software cannot manufacture partner truth. Frequency, financial impact, primary user, escalation rules, and the strongest wedge (containment, reconstruction, deployment compatibility, or remote diagnostics) require interviews and observed incident reviews. Record those findings as evidence; do not present assumptions as validated partner claims.
