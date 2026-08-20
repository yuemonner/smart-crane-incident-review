# Smart Crane Decision Review Pilot

This is a read-only design-partner pilot prototype for Smart Crane / connected industrial equipment decision reviews. It turns one high-cost machine decision into a fleet-wide **WHERE ELSE?** assessment while clearly separating confirmed evidence, unestablished claims, counterevidence, and evidence gaps.

The proposed 4-week pilot operating model is:

1. Reconstruct what happened and the machine state around the event.
2. Establish the last known good software/configuration/runtime/test state when explicit evidence exists.
3. Identify what changed.
4. Compare device-specific evidence with peer devices and deployment cohorts.
5. Support a human test / rollback / redeploy / hold decision.
6. Preserve what the team knew at the time, what it decided, and what happened next.
7. Identify what must be captured next time so the next review is reconstructable.

The application does not assume machines fail frequently. It addresses the high cost of reconstructing context when an unusual event, risky production change, return-to-service decision, rollback, redeploy, inspection, configuration change, or maintenance intervention does require review.

## Pilot question

Can a read-only system of context reduce the time required to reconstruct machine decision context, identify peer exposure, preserve the knowledge state at the time of decision, and specify what must be captured next time?

The pilot is not trying to replace telemetry, Azure DevOps, maintenance systems, or operator workflow. It is testing whether evidence across those systems can be reconstructed into a decision review that is useful to engineering, service, and operations together.

## Architecture boundary

This application is a **system of context**, not a replacement system of record:

- Continuous high-volume telemetry remains in the telemetry platform.
- A bounded operational trace holds only the recent context that may be difficult to reconstruct later.
- A critical trigger freezes a review snapshot containing version/configuration, operating mode, critical state, state diff, recent actions, related IDs, and intervention context.
- Manual interventions and configuration changes can be appended as explicit audit events.
- A local evidence ledger preserves normalized non-demo evidence in an append-only table with a verifiable hash chain.
- Source systems continue to own deployment, telemetry, ticket, and maintenance truth.

Every normalized record distinguishes `observed`, `inferred`, and `human_asserted` evidence. Inferred records may carry confidence. A later record can supersede an earlier record without deleting it.

The ledger detects application-level mutation; it is not hardware-backed immutability and does not establish source integrity, clock accuracy, sensor calibration, or legal chain of custody.

When a human decision is recorded, the application also freezes the observed facts, supported assessment, assumptions, unknowns, and evidence IDs available at that time. Later evidence can change the current conclusion without rewriting that historical decision context.

## Reconstruction Engine V0

The backend now includes a portable reconstruction core that does not depend on private customer data or any single ICP.

It proves five reusable capabilities:

1. **Canonical evidence schema** — normalizes records into `event_time`, `observed_at`, `ingested_at`, `assertion_type`, provenance, subject, before and after.
2. **Temporal state reconstruction** — answers what could be proven about an asset at a decision time without using evidence that arrived later.
3. **Change detection** — returns what changed in the lookback window with source, timestamp and evidence strength, without claiming cause.
4. **Reconstructability analysis** — marks fields as `COMPLETE`, `PARTIAL` or `MISSING` and recommends minimum future capture.
5. **Peer context matching** — finds assets with the same firmware/config signature, matching precursor signals and counterexamples.

It also introduces three backend primitives for the operational learning layer:

- **ContextSignature** — the reusable fingerprint of firmware, configuration, precursor signal, alarm, missing fields and source evidence.
- **OperationalEpisode** — the reviewed unit of machine state, knowledge state, intervention, human decision and outcome.
- **OutcomeRecord** — the follow-up result attached to a decision episode, used for future retrieval and learning.

The synthetic world creates 50 cranes with mixed firmware, configuration, telemetry, human assertions, late-arriving counterevidence and missing intervention context. It exists to test reconstruction logic before connecting proprietary customer systems.

Run the portable backend report:

```powershell
curl http://127.0.0.1:8010/api/reconstruction/demo
```

Run the live reconstruction demo:

```powershell
curl "http://127.0.0.1:8010/api/reconstruction/live-demo?step=9"
```

Run the operational learning report:

```powershell
curl http://127.0.0.1:8010/api/reconstruction/learning
```

The live demo advances through a representative smart-crane review:

```text
machine change
→ automatic review creation
→ what-changed reconstruction
→ observed / human-asserted / inferred / not-established evidence
→ bounded AI interpretation
→ fleet WHERE ELSE? comparison
→ reconstructability gap check
→ frozen human decision
→ late evidence updates the current conclusion without rewriting the historical decision context
→ peer failure changes the current fleet view while the 16:05 decision remains frozen
→ historical outcome comparison shows what similar reviewed contexts produced
```

The AI reasoning layer is deliberately constrained: backend reconstruction determines what happened, rules classify evidence status, AI explains already reconstructed evidence, and humans record the decision. The final learning view is historical outcomes, not a recommendation.

The eval suite checks that the engine:

- reconstructs firmware/configuration at incident time;
- does not use evidence discovered after the decision time;
- distinguishes observed evidence from human assertion;
- detects missing intervention reason;
- produces before/after config diff;
- finds exposed peer assets;
- includes counterexamples;
- avoids promoting correlation to causation;
- preserves a superseded hypothesis as historical knowledge state;
- generates minimum capture recommendations.

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

## Optional live Smart Crane PostgreSQL evidence

Create an SSH tunnel to the edge host, then set the `SMART_CRANE_POSTGRES_*` values shown in `.env.example`. Use only a dedicated account with `SELECT` grants and `default_transaction_read_only=on`.

The connector independently forces every database session into read-only mode. It runs fixed, bounded queries against only `faults` and `notifications`; it explicitly excludes `edge_users` and exposes no arbitrary SQL facility. Check the connection with `GET /api/sources`, then ingest normalized evidence with `POST /api/sources/postgres/refresh`.

## Optional live Cosmos physical telemetry

Set the `SMART_CRANE_COSMOS_*` values in `.env` using a dedicated read-only Cassandra identity. `POST /api/sources/cosmos/refresh` runs one bounded `SELECT` against `cloud_core.crane_telemetry` for a selected edge UUID and time window. It normalizes physical fields such as drive alarms/faults, load, current, torque, output frequency, temperature, and drive-ready state. No generic CQL endpoint and no write operation exist.

Browser access to Azure Portal is not treated as an application credential. Until the Cassandra connection succeeds, the UI says telemetry is offline. Per-row hashes document the retrieved normalized content, but do **not** prove source immutability, clock accuracy, sensor calibration, or legal chain of custody.

## Evidence modes and memory

Demo, cached, partial, and live records are separate workspaces. Queries never silently combine them. The incident selector is generated from alarm records in the selected mode. Source retrieval timestamps and integrity limitations are shown beside evidence.

Human-recorded owner, checkpoint, and explicit decision fields are stored in `work/incident_memory.sqlite3`. This is local application memory only; it never writes to Smart Crane Cloud, ADO, databases, or devices.

## Core endpoints

- `POST /api/incidents/investigate` reconstructs a bounded evidence timeline and WHAT CHANGED context.
- `POST /api/incidents/where-else` derives a traceable exposure signature and ranks peer assets.
- `GET /api/incidents?mode=live` lists real selectable alarm incidents for one evidence mode.
- `GET /api/fleet/identity` returns the last live REST identity mapping for cranes, customers, and sites.
- `PUT /api/memory/incidents/{id}` saves a local human decision record.
- `GET /api/demo` returns the complete zero-configuration demo.
- `GET /api/reconstruction/demo` returns the portable Reconstruction Engine V0 report.
- `GET /api/reconstruction/live-demo?step=9` returns a stepwise live reconstruction scenario for the product demo.
- `GET /api/reconstruction/learning` returns the operational episode, similar-context learning report, and context graph.
- `GET /api/health` reports local service status.
- `GET /api/sources` reports ADO, Smart Crane source-contract, and fleet-telemetry connection truthfully.
- `POST /api/sources/ado/refresh` ingests current ADO evidence into the normalized evidence store.
- `POST /api/sources/local/refresh` ingests timestamped Smart Crane engineering/log evidence while excluding connection notes and secret-bearing lines.
- `POST /api/sources/postgres/refresh` ingests bounded live Smart Crane fault and notification evidence using an enforced read-only session.
- `POST /api/sources/cosmos/refresh` ingests bounded live physical telemetry for one crane and time window.
- `POST /api/capture/trace` adds a lightweight sample to the bounded operational ring buffer.
- `POST /api/capture/critical-snapshot` freezes a critical machine-decision snapshot and appends it to the evidence ledger.
- `POST /api/capture/audit-event` appends an explicit manual intervention/configuration audit event.
- `GET /api/capture/status` reports buffer ownership, capacity, and ledger verification status.
- `GET /api/ledger/status` verifies the local evidence hash chain and states its integrity limitations.

Example request body:

```json
{"entity_id":"Crane-07","incident_time":"2026-08-14T14:32:00Z","window_hours":72,"evidence_mode":"demo"}
```

## Validation still required

Software cannot manufacture partner truth. Frequency, financial impact, primary user, escalation rules, and the strongest wedge (containment, reconstruction, deployment compatibility, or remote diagnostics) require interviews and observed incident reviews. Record those findings as evidence; do not present assumptions as validated partner claims.
