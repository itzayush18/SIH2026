"""
OilTrace — In-memory data store.

Provides a lightweight storage layer for the scaffold pass.
Uses Python dicts for fast iteration; DuckDB for persistence later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from packages.schemas.models import (
    Case,
    CaseStatus,
    DetectionRun,
    DriftRun,
    JobState,
    JobStatus,
    Slick,
    SourceAsset,
    AuditEvent,
)


class Store:
    """In-memory store for all OilTrace entities."""

    def __init__(self) -> None:
        self.cases: dict[str, Case] = {}
        self.assets: dict[str, SourceAsset] = {}
        self.detection_runs: dict[str, DetectionRun] = {}
        self.slicks: dict[str, Slick] = {}
        self.drift_runs: dict[str, DriftRun] = {}
        self.jobs: dict[str, JobStatus] = {}
        self.audit_events: list[AuditEvent] = []

    # -- Cases ---------------------------------------------------------

    def create_case(self, case: Case) -> Case:
        self.cases[case.case_id] = case
        return case

    def get_case(self, case_id: str) -> Optional[Case]:
        return self.cases.get(case_id)

    def update_case_status(self, case_id: str, status: CaseStatus) -> Optional[Case]:
        case = self.cases.get(case_id)
        if case:
            case.status = status
        return case

    # -- Assets --------------------------------------------------------

    def add_asset(self, asset: SourceAsset) -> SourceAsset:
        self.assets[asset.asset_id] = asset
        return asset

    def get_assets_for_case(self, case_id: str) -> list[SourceAsset]:
        return [a for a in self.assets.values() if a.case_id == case_id]

    # -- Detection Runs ------------------------------------------------

    def add_detection_run(self, run: DetectionRun) -> DetectionRun:
        self.detection_runs[run.run_id] = run
        return run

    def get_detection_run(self, run_id: str) -> Optional[DetectionRun]:
        return self.detection_runs.get(run_id)

    # -- Slicks --------------------------------------------------------

    def add_slick(self, slick: Slick) -> Slick:
        self.slicks[slick.slick_id] = slick
        return slick

    def get_slicks_for_case(self, case_id: str) -> list[Slick]:
        return [s for s in self.slicks.values() if s.case_id == case_id]

    def get_slicks_for_run(self, run_id: str) -> list[Slick]:
        return [s for s in self.slicks.values() if s.run_id == run_id]

    # -- Drift Runs ----------------------------------------------------

    def add_drift_run(self, drift: DriftRun) -> DriftRun:
        self.drift_runs[drift.drift_id] = drift
        return drift

    def get_drift_runs_for_case(self, case_id: str) -> list[DriftRun]:
        return [d for d in self.drift_runs.values() if d.case_id == case_id]

    # -- Jobs ----------------------------------------------------------

    def create_job(self, job_id: str, message: str = "") -> JobStatus:
        job = JobStatus(
            job_id=job_id,
            state=JobState.queued,
            message=message,
        )
        self.jobs[job_id] = job
        return job

    def complete_job(self, job_id: str, message: str = "Done") -> Optional[JobStatus]:
        job = self.jobs.get(job_id)
        if job:
            job.state = JobState.completed
            job.progress = 1.0
            job.message = message
            job.completed_at = datetime.utcnow()
        return job

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        return self.jobs.get(job_id)

    # -- Audit ---------------------------------------------------------

    def append_audit(self, event: AuditEvent) -> None:
        self.audit_events.append(event)


# Module-level singleton — imported by routes
store = Store()
