from __future__ import annotations

from pathlib import Path

from app.core.config import settings


class StorageBackend:
    def save(self, relative_path: str, content: bytes) -> str:
        raise NotImplementedError

    def resolve_path(self, relative_path: str) -> Path:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.storage_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, content: bytes) -> str:
        full_path = self.base_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return str(full_path)

    def resolve_path(self, relative_path: str) -> Path:
        return self.base_dir / relative_path


_default_backend = LocalStorageBackend()


def get_storage_backend() -> StorageBackend:
    return _default_backend
