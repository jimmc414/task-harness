"""Tests for history infrastructure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.history import RunHistory
from harness.models import RunRecord


class TestRunHistory:
    """Tests for RunHistory."""

    @pytest.fixture
    def history(self, tmp_path: Path) -> RunHistory:
        """Create a history instance with temp file."""
        return RunHistory(tmp_path / "test_history.jsonl")

    @pytest.fixture
    def sample_records(self) -> list[RunRecord]:
        """Create sample run records."""
        return [
            RunRecord(
                run_id="run-001",
                pipeline_name="pipeline_a",
                status="success",
                started_at="2024-01-01T10:00:00+00:00",
                completed_at="2024-01-01T10:01:00+00:00",
                tasks_completed=3,
            ),
            RunRecord(
                run_id="run-002",
                pipeline_name="pipeline_a",
                status="failed",
                started_at="2024-01-02T10:00:00+00:00",
                completed_at="2024-01-02T10:00:30+00:00",
                tasks_completed=1,
                tasks_failed=1,
                error_message="Task failed",
            ),
            RunRecord(
                run_id="run-003",
                pipeline_name="pipeline_b",
                status="success",
                started_at="2024-01-03T10:00:00+00:00",
                completed_at="2024-01-03T10:02:00+00:00",
                tasks_completed=5,
            ),
        ]

    def test_record_and_retrieve(self, history: RunHistory) -> None:
        """Should record and retrieve a run."""
        record = RunRecord(
            pipeline_name="test_pipeline",
            status="success",
        )
        history.record(record)

        all_records = history.get_all()
        assert len(all_records) == 1
        assert all_records[0].pipeline_name == "test_pipeline"

    def test_get_recent(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should get recent records in reverse order."""
        for record in sample_records:
            history.record(record)

        recent = history.get_recent(limit=2)

        assert len(recent) == 2
        # Newest first
        assert recent[0].run_id == "run-003"
        assert recent[1].run_id == "run-002"

    def test_filter_by_pipeline(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should filter by pipeline name."""
        for record in sample_records:
            history.record(record)

        filtered = history.get_recent(pipeline="pipeline_a")

        assert len(filtered) == 2
        assert all(r.pipeline_name == "pipeline_a" for r in filtered)

    def test_filter_by_status(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should filter by status."""
        for record in sample_records:
            history.record(record)

        filtered = history.get_recent(status="success")

        assert len(filtered) == 2
        assert all(r.status == "success" for r in filtered)

    def test_get_by_run_id(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should find record by run ID."""
        for record in sample_records:
            history.record(record)

        found = history.get_by_run_id("run-002")

        assert found is not None
        assert found.run_id == "run-002"
        assert found.status == "failed"

    def test_get_by_run_id_not_found(self, history: RunHistory) -> None:
        """Should return None for missing run ID."""
        assert history.get_by_run_id("nonexistent") is None

    def test_get_by_pipeline(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should get all runs for a pipeline."""
        for record in sample_records:
            history.record(record)

        runs = history.get_by_pipeline("pipeline_a")

        assert len(runs) == 2
        assert all(r.pipeline_name == "pipeline_a" for r in runs)

    def test_get_last_run(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should get most recent run for a pipeline."""
        for record in sample_records:
            history.record(record)

        last = history.get_last_run("pipeline_a")

        assert last is not None
        assert last.run_id == "run-002"  # Most recent for pipeline_a

    def test_get_last_run_not_found(self, history: RunHistory) -> None:
        """Should return None for pipeline with no runs."""
        assert history.get_last_run("nonexistent") is None

    def test_count(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should count records correctly."""
        for record in sample_records:
            history.record(record)

        assert history.count() == 3
        assert history.count(pipeline="pipeline_a") == 2
        assert history.count(status="success") == 2
        assert history.count(pipeline="pipeline_a", status="failed") == 1

    def test_get_stats(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should calculate statistics correctly."""
        for record in sample_records:
            history.record(record)

        stats = history.get_stats()

        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_get_stats_by_pipeline(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should calculate stats for specific pipeline."""
        for record in sample_records:
            history.record(record)

        stats = history.get_stats(pipeline_name="pipeline_a")

        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["failed"] == 1

    def test_clear(self, history: RunHistory, sample_records: list[RunRecord]) -> None:
        """Should clear all history."""
        for record in sample_records:
            history.record(record)

        assert history.count() == 3

        history.clear()

        assert history.count() == 0
        assert not history.history_file.exists()

    def test_empty_history(self, history: RunHistory) -> None:
        """Should handle empty history file."""
        assert history.get_all() == []
        assert history.get_recent() == []
        assert history.count() == 0

    def test_handles_malformed_lines(self, tmp_path: Path) -> None:
        """Should skip malformed JSON lines."""
        history_file = tmp_path / "history.jsonl"
        history_file.write_text(
            '{"run_id": "valid", "pipeline_name": "test", "status": "success"}\n'
            'not valid json\n'
            '{"run_id": "also_valid", "pipeline_name": "test", "status": "failed"}\n'
        )

        history = RunHistory(history_file)
        records = history.get_all()

        assert len(records) == 2

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Should create parent directory if it doesn't exist."""
        history = RunHistory(tmp_path / "nested" / "dir" / "history.jsonl")
        record = RunRecord(pipeline_name="test")

        history.record(record)

        assert history.history_file.exists()

    def test_preserves_all_fields(self, history: RunHistory) -> None:
        """Should preserve all record fields through serialization."""
        original = RunRecord(
            run_id="run-test",
            pipeline_name="test_pipeline",
            status="failed",
            started_at="2024-01-01T10:00:00+00:00",
            completed_at="2024-01-01T10:01:00+00:00",
            tasks_completed=5,
            tasks_failed=2,
            tasks_skipped=1,
            error_message="Something went wrong",
            dry_run=True,
        )

        history.record(original)
        retrieved = history.get_all()[0]

        assert retrieved.run_id == original.run_id
        assert retrieved.pipeline_name == original.pipeline_name
        assert retrieved.status == original.status
        assert retrieved.started_at == original.started_at
        assert retrieved.completed_at == original.completed_at
        assert retrieved.tasks_completed == original.tasks_completed
        assert retrieved.tasks_failed == original.tasks_failed
        assert retrieved.tasks_skipped == original.tasks_skipped
        assert retrieved.error_message == original.error_message
        assert retrieved.dry_run == original.dry_run
