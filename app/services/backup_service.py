from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.core.config import Settings, get_settings
from app.core.database import PROJECT_ROOT

SENSITIVE_BACKUP_EXCLUSIONS = (
    ".env",
    "gmail_token.json",
    "google_calendar_token.json",
    "microsoft_graph_token.json",
    "client_secret.json",
)

DOC_BACKUP_FILES = (
    "README.md",
    "docs/HELP.md",
    "docs/PHASE_STATUS.md",
    "docs/IMPLEMENTATION_LOG.md",
    "docs/LESSONS_LEARNED.md",
)


@dataclass(frozen=True)
class BackupMetadata:
    backup_path: str
    created_at: datetime
    included_files: tuple[str, ...]
    excluded_sensitive_files: tuple[str, ...]
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "backup_path": self.backup_path,
            "created_at": self.created_at.isoformat(),
            "included_files": list(self.included_files),
            "excluded_sensitive_files": list(self.excluded_sensitive_files),
            "size_bytes": self.size_bytes,
        }


def create_local_backup(settings: Settings | None = None) -> BackupMetadata:
    active = settings or get_settings()
    created_at = datetime.now(UTC)
    backups_dir = PROJECT_ROOT / "_backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = created_at.strftime("%Y%m%d-%H%M%S")
    archive_path = backups_dir / f"commsdesk-backup-{stamp}.zip"
    included: list[str] = []
    excluded = _existing_sensitive_files()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        db_path = sqlite_database_path(active)
        if db_path and db_path.exists():
            temp_db = backups_dir / f"commsdesk-{stamp}.db"
            shutil.copy2(db_path, temp_db)
            archive.write(temp_db, arcname=db_path.name)
            included.append(db_path.name)
            temp_db.unlink(missing_ok=True)
        env_example = PROJECT_ROOT / ".env.example"
        if env_example.exists():
            archive.write(env_example, arcname=".env.example")
            included.append(".env.example")
        for rel in DOC_BACKUP_FILES:
            path = PROJECT_ROOT / rel
            if path.exists():
                archive.write(path, arcname=rel)
                included.append(rel)

    return BackupMetadata(
        backup_path=str(archive_path),
        created_at=created_at,
        included_files=tuple(included),
        excluded_sensitive_files=excluded,
        size_bytes=archive_path.stat().st_size if archive_path.exists() else 0,
    )


def latest_backup_metadata() -> BackupMetadata | None:
    backups_dir = PROJECT_ROOT / "_backups"
    archives = sorted(backups_dir.glob("commsdesk-backup-*.zip"), key=lambda p: p.stat().st_mtime)
    if not archives:
        return None
    path = archives[-1]
    created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return BackupMetadata(
        backup_path=str(path),
        created_at=created_at,
        included_files=tuple(_zip_names(path)),
        excluded_sensitive_files=_existing_sensitive_files(),
        size_bytes=path.stat().st_size,
    )


def list_backups(limit: int = 20) -> list[BackupMetadata]:
    backups_dir = PROJECT_ROOT / "_backups"
    archives = sorted(
        backups_dir.glob("commsdesk-backup-*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for path in archives[:limit]:
        rows.append(
            BackupMetadata(
                backup_path=str(path),
                created_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                included_files=tuple(_zip_names(path)),
                excluded_sensitive_files=_existing_sensitive_files(),
                size_bytes=path.stat().st_size,
            )
        )
    return rows


def sqlite_database_path(settings: Settings | None = None) -> Path | None:
    active = settings or get_settings()
    parsed = urlparse(active.database_url)
    if parsed.scheme not in {"sqlite", "sqlite+pysqlite"}:
        return None
    raw = unquote(parsed.path or "")
    if raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
        path = Path(raw.lstrip("/"))
    elif raw:
        path = Path(raw)
    else:
        path = Path(parsed.netloc)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _existing_sensitive_files() -> tuple[str, ...]:
    return tuple(name for name in SENSITIVE_BACKUP_EXCLUSIONS if (PROJECT_ROOT / name).exists())


def _zip_names(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            return sorted(archive.namelist())
    except zipfile.BadZipFile:
        return []
