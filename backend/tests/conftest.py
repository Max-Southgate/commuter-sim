import pytest

from app import config


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty DuckDB file / cache dir - never touches data/."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    yield tmp_path


@pytest.fixture
def settings():
    import yaml

    path = config.CONFIG_DIR / "routes.example.yaml"
    return config.parse_settings(yaml.safe_load(path.read_text(encoding="utf-8")), path)
