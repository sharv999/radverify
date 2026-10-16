from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


DEFAULT_CLIENT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "clients.json"


def _normalise_client_name(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def load_clients(path: str | Path | None = None) -> list[str]:
    """Load the persisted client-name database, tolerating a missing/empty file."""
    target = Path(path) if path is not None else DEFAULT_CLIENT_DATABASE_PATH
    if not target.exists():
        return []

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_clients = payload.get("clients", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_clients, list):
        return []

    seen: set[str] = set()
    clients: list[str] = []
    for raw in raw_clients:
        name = _normalise_client_name(raw)
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        clients.append(name)
    return sorted(clients, key=str.casefold)


def save_clients(clients: Iterable[object], path: str | Path | None = None) -> list[str]:
    """Persist a de-duplicated, alphabetically sorted client-name database."""
    target = Path(path) if path is not None else DEFAULT_CLIENT_DATABASE_PATH
    normalised: dict[str, str] = {}
    for raw in clients:
        name = _normalise_client_name(raw)
        if name:
            normalised.setdefault(name.casefold(), name)
    stored = sorted(normalised.values(), key=str.casefold)

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps({"clients": stored}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return stored


def add_client(name: object, path: str | Path | None = None) -> tuple[list[str], str]:
    """Add a client if absent; return the updated list and canonical stored name."""
    candidate = _normalise_client_name(name)
    if not candidate:
        raise ValueError("Client name cannot be blank.")

    clients = load_clients(path)
    for existing in clients:
        if existing.casefold() == candidate.casefold():
            return clients, existing

    clients.append(candidate)
    stored = save_clients(clients, path)
    canonical = next(item for item in stored if item.casefold() == candidate.casefold())
    return stored, canonical


def delete_client(name: object, path: str | Path | None = None) -> list[str]:
    """Delete a client by case-insensitive name and persist the updated database."""
    candidate = _normalise_client_name(name)
    if not candidate:
        return load_clients(path)
    clients = [item for item in load_clients(path) if item.casefold() != candidate.casefold()]
    return save_clients(clients, path)
