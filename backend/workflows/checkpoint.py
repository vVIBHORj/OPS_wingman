"""
Workflow Checkpointing and State Persistence (Phase 2 - Deliverable D-09).
Durable, thread-safe persistence for workflow runs and execution steps.
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timezone


from backend.workflows.state import WorkflowRunRecord, WorkflowState, WorkflowStepRecord

DEFAULT_CHECKPOINT_DIR = Path(os.getenv("CHECKPOINT_DIR", ".data/checkpoints"))


class WorkflowCheckpointStore:
    """
    Durable, thread-safe store for workflow execution checkpoints.
    Persists runs in-memory and automatically flushes to disk for process restart durability.
    """

    def __init__(self, storage_dir: Optional[Union[str, Path]] = DEFAULT_CHECKPOINT_DIR) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, WorkflowRunRecord] = {}
        self.storage_dir: Optional[Path] = Path(storage_dir) if storage_dir else None

        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _get_file_path(self, run_id: str) -> Optional[Path]:
        if not self.storage_dir:
            return None
        return self.storage_dir / f"{run_id}.json"

    def _load_from_disk(self) -> None:
        """Loads all existing checkpoints from the persistence directory on initialization."""
        if not self.storage_dir or not self.storage_dir.exists():
            return
        for file_path in self.storage_dir.glob("*.json"):
            try:
                content = file_path.read_text(encoding="utf-8")
                run = WorkflowRunRecord.model_validate_json(content)
                self._runs[run.run_id] = run
            except Exception:
                pass

    def save(self, run: WorkflowRunRecord) -> WorkflowRunRecord:
        """Saves or updates a workflow run record in memory and durable storage."""
        with self._lock:
            run.updated_at = datetime.now(timezone.utc)
            self._runs[run.run_id] = run

            if self.storage_dir:
                try:
                    file_path = self._get_file_path(run.run_id)
                    if file_path:
                        tmp_path = file_path.with_suffix(".tmp")
                        tmp_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
                        tmp_path.replace(file_path)
                except Exception:
                    pass

            return run

    def get(self, run_id: str) -> Optional[WorkflowRunRecord]:
        """Retrieves a workflow run by run_id from memory or disk."""
        with self._lock:
            if run_id in self._runs:
                return self._runs[run_id]

            if self.storage_dir:
                file_path = self._get_file_path(run_id)
                if file_path and file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        run = WorkflowRunRecord.model_validate_json(content)
                        self._runs[run.run_id] = run
                        return run
                    except Exception:
                        return None

            return None

    def list_runs(self, limit: int = 50) -> List[WorkflowRunRecord]:
        """Lists recent workflow runs sorted by last update time."""
        with self._lock:
            # Sync any new files from disk if needed
            if self.storage_dir and self.storage_dir.exists():
                for file_path in self.storage_dir.glob("*.json"):
                    r_id = file_path.stem
                    if r_id not in self._runs:
                        try:
                            content = file_path.read_text(encoding="utf-8")
                            run = WorkflowRunRecord.model_validate_json(content)
                            self._runs[run.run_id] = run
                        except Exception:
                            pass

            return sorted(self._runs.values(), key=lambda r: r.updated_at, reverse=True)[:limit]

    def add_step(
        self,
        run_id: str,
        step_name: str,
        state: WorkflowState,
        tool_name: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[WorkflowRunRecord]:
        """Appends an execution step record to a run."""
        run = self.get(run_id)
        if not run:
            return None

        step = WorkflowStepRecord(
            step_name=step_name,
            state=state,
            tool_name=tool_name,
            input_payload=input_payload,
            output_payload=output_payload,
            error=error,
        )
        run.steps.append(step)
        run.state = state
        return self.save(run)

    def clear(self, clear_disk: bool = False) -> None:
        """Clears memory cache and optionally deletes persistent disk checkpoints."""
        with self._lock:
            self._runs.clear()
            if clear_disk and self.storage_dir and self.storage_dir.exists():
                for file_path in self.storage_dir.glob("*.json"):
                    try:
                        file_path.unlink()
                    except Exception:
                        pass


# Default singleton instance with durable persistence
checkpoint_store = WorkflowCheckpointStore()

