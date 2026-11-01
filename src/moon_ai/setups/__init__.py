"""ICT setups: one module per setup, each registering a `Setup` that emits `Candidate`s."""

# Importing a setup module registers it in REGISTRY.
from moon_ai.setups import london, ote, silver_bullet  # noqa: F401
from moon_ai.setups.base import (
    DEFAULTS_PATH,
    MAX_RESCUE_TRIALS,
    REGISTRY,
    Candidate,
    RescueTrial,
    Setup,
    SetupDefaults,
    SetupParams,
    defaults_hash,
    load_setup_defaults,
    register,
)

__all__ = [
    "DEFAULTS_PATH",
    "MAX_RESCUE_TRIALS",
    "REGISTRY",
    "Candidate",
    "RescueTrial",
    "Setup",
    "SetupDefaults",
    "SetupParams",
    "defaults_hash",
    "load_setup_defaults",
    "register",
]
