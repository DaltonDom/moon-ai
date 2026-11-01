import pytest


@pytest.fixture(autouse=True)
def _no_real_credentials(monkeypatch):
    """Tests never reach Claude or GitHub, even on a Mac where the keys are set."""
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
