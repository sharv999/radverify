from pathlib import Path

from services.client_database import add_client, delete_client, load_clients, save_clients


def test_client_database_adds_deduplicates_sorts_and_deletes(tmp_path: Path):
    path = tmp_path / "clients.json"
    save_clients(["Zulu Health", "Alpha Imaging"], path)
    clients, canonical = add_client("  Beta   Medical  ", path)
    assert canonical == "Beta Medical"
    assert clients == ["Alpha Imaging", "Beta Medical", "Zulu Health"]

    clients, canonical = add_client("beta medical", path)
    assert canonical == "Beta Medical"
    assert clients == ["Alpha Imaging", "Beta Medical", "Zulu Health"]

    assert delete_client("BETA MEDICAL", path) == ["Alpha Imaging", "Zulu Health"]
    assert load_clients(path) == ["Alpha Imaging", "Zulu Health"]


def test_client_database_missing_file_is_empty(tmp_path: Path):
    assert load_clients(tmp_path / "missing.json") == []
