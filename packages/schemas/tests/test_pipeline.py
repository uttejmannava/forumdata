"""Tests for pipeline models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from forum_schemas.models.pipeline import (
    NavigationMode,
    Pipeline,
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    PipelineType,
    RunStatus,
    StealthLevel,
)


class TestPipelineConfig:
    def test_defaults(self) -> None:
        config = PipelineConfig()
        assert config.navigation_mode == NavigationMode.SINGLE_PAGE
        assert config.stealth_level == StealthLevel.NONE
        assert config.max_tabs == 5
        assert config.resource_blocking_enabled is True

    def test_max_tabs_bounds(self) -> None:
        with pytest.raises(ValidationError):
            PipelineConfig(max_tabs=0)
        with pytest.raises(ValidationError):
            PipelineConfig(max_tabs=21)


class TestPipeline:
    def test_create_minimal(self) -> None:
        p = Pipeline(tenant_id=uuid4(), name="CME Settlements", source_url="https://cme.com", created_by="test")
        assert p.status == PipelineStatus.DRAFT
        assert p.pipeline_type == PipelineType.EXTRACTION

    def test_name_validation(self) -> None:
        with pytest.raises(ValidationError):
            Pipeline(tenant_id=uuid4(), name="", source_url="https://cme.com", created_by="test")


class TestPipelineRun:
    def test_defaults(self) -> None:
        run = PipelineRun(pipeline_id=uuid4(), tenant_id=uuid4())
        assert run.status == RunStatus.PENDING
        assert run.trigger == "scheduled"
        assert run.errors == []
        assert run.warnings == []


class TestEnums:
    def test_navigation_modes(self) -> None:
        assert len(NavigationMode) == 6

    def test_stealth_levels(self) -> None:
        assert len(StealthLevel) == 4

    def test_pipeline_types(self) -> None:
        assert len(PipelineType) == 3
