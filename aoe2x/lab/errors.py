"""Typed failures surfaced by the AOE2 Lab CLI and persisted in job state."""


class LabError(RuntimeError):
    """Base class for an actionable, user-facing lab failure."""

    code = "LAB_ERROR"

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


class ConfigurationError(LabError):
    code = "CONFIGURATION_ERROR"


class PreflightError(LabError):
    code = "PREFLIGHT_ERROR"


class PlanError(LabError):
    code = "PLAN_ERROR"


class SimulationError(LabError):
    code = "SIMULATION_ERROR"


class LiveCaptureError(LabError):
    code = "LIVE_CAPTURE_ERROR"


class ComparisonError(LabError):
    code = "COMPARISON_ERROR"


class PublicationError(LabError):
    code = "PUBLICATION_ERROR"
