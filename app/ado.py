import base64
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from .models import EvidenceEvent, EvidenceMode, EvidenceType, IntegrityStatus


class AzureDevOpsReadOnlyConnector:
    """ADO adapter that performs retrieval operations only."""

    def __init__(self, org: str, project: str, pat: str):
        self.org, self.project = org, project
        self.base = f"https://dev.azure.com/{quote(org)}/{quote(project)}/_apis"
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        params = {**(params or {}), "api-version": "7.1"}
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(f"{self.base}/{path}", params=params)
            response.raise_for_status()
            return response.json()

    async def status(self) -> dict:
        data = await self._get("git/repositories")
        return {"connected": True, "organization": self.org, "project": self.project,
                "repository_count_visible": data.get("count", len(data.get("value", [])))}

    def _common(self, retrieved_at):
        return {"retrieved_at": retrieved_at, "evidence_mode": EvidenceMode.live,
                "integrity": IntegrityStatus(transport="HTTPS",
                    limitation="Normalized from an ADO REST response; source history integrity was not independently attested.")}

    async def collect(self, limit_per_repo: int = 20) -> list[EvidenceEvent]:
        retrieved_at = datetime.now(timezone.utc)
        common = self._common(retrieved_at)
        repos = (await self._get("git/repositories")).get("value", [])
        events: list[EvidenceEvent] = []
        for repo in repos:
            rid, name = repo["id"], repo["name"]
            commits = (await self._get(f"git/repositories/{rid}/commits",
                {"searchCriteria.$top": limit_per_repo})).get("value", [])
            for item in commits:
                events.append(EvidenceEvent(id=f"ADO-COMMIT-{item['commitId']}", type=EvidenceType.commit,
                    occurred_at=item["author"]["date"], title=item.get("comment", "Commit"),
                    source=f"Azure DevOps · {name}", source_url=item.get("remoteUrl"), **common,
                    attributes={"repository": name, "repository_id": rid,
                                "commit": item["commitId"], "author": item["author"].get("name")}))
            prs = (await self._get(f"git/repositories/{rid}/pullrequests",
                {"searchCriteria.status": "all", "$top": limit_per_repo})).get("value", [])
            for item in prs:
                events.append(EvidenceEvent(id=f"ADO-PR-{item['pullRequestId']}",
                    type=EvidenceType.pull_request, occurred_at=item["creationDate"], title=item["title"],
                    source=f"Azure DevOps · {name}", **common,
                    source_url=f"https://dev.azure.com/{self.org}/{quote(self.project)}/_git/{quote(name)}/pullrequest/{item['pullRequestId']}",
                    attributes={"repository": name, "pull_request_id": item["pullRequestId"],
                                "status": item.get("status"),
                                "created_by": item.get("createdBy", {}).get("displayName")}))
        builds = (await self._get("build/builds", {"$top": 50,
            "queryOrder": "finishTimeDescending"})).get("value", [])
        seen_work_items: set[str] = set()
        for item in builds:
            timestamp = item.get("finishTime") or item.get("queueTime") or retrieved_at
            events.append(EvidenceEvent(id=f"ADO-BUILD-{item['id']}", type=EvidenceType.build,
                occurred_at=timestamp,
                title=f"{item.get('definition', {}).get('name', 'Pipeline')} · {item.get('buildNumber')}",
                source="Azure Pipelines", source_url=item.get("_links", {}).get("web", {}).get("href"),
                **common, attributes={"build_id": item["id"], "result": item.get("result"),
                    "status": item.get("status"), "source_version": item.get("sourceVersion"),
                    "repository": item.get("repository", {}).get("name")}))
            try:
                refs = (await self._get(f"build/builds/{item['id']}/workitems")).get("value", [])
            except (httpx.HTTPStatusError, AssertionError):
                refs = []
            for ref in refs[:20]:
                wid = str(ref.get("id", ""))
                if not wid or wid in seen_work_items:
                    continue
                seen_work_items.add(wid)
                detail = await self._get(f"wit/workitems/{wid}")
                fields = detail.get("fields", {})
                assigned = fields.get("System.AssignedTo") or {}
                events.append(EvidenceEvent(id=f"ADO-WORKITEM-{wid}", type=EvidenceType.work_item,
                    occurred_at=fields.get("System.ChangedDate") or timestamp,
                    title=fields.get("System.Title", f"Work item {wid}"), source="Azure Boards",
                    source_url=detail.get("_links", {}).get("html", {}).get("href"), **common,
                    attributes={"work_item_id": wid, "state": fields.get("System.State"),
                        "owner": assigned.get("displayName") if isinstance(assigned, dict) else assigned,
                        "checkpoint_at": fields.get("Microsoft.VSTS.Scheduling.TargetDate"),
                        "work_item_type": fields.get("System.WorkItemType"),
                        "linked_build_id": item["id"]}))
        return events
