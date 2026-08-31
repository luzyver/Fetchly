import pytest


@pytest.fixture(autouse=True)
def isolate_download_root(settings, tmp_path):
    settings.DOWNLOAD_ROOT = tmp_path / "downloads"
    settings.DOWNLOAD_ROOT.mkdir()
