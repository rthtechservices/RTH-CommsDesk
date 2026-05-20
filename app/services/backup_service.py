from __future__ import annotations

import json
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
    database_included: bool = False
    oauth_tokens_included: bool = False
    env_snapshot_status: str = "redacted"

    @property
    def filename(self) -> str:
        return Path(self.backup_path).name

    def as_dict(self) -> dict[str, object]:
        return {
            "backup_path": self.backup_path,
            "created_at": self.created_at.isoformat(),
            "included_files": list(self.included_files),
            "excluded_sensitive_files": list(self.excluded_sensitive_files),
            "size_bytes": self.size_bytes,
            "filename": self.filename,
            "database_included": self.database_included,
            "oauth_tokens_included": self.oauth_tokens_included,
            "env_snapshot_status": self.env_snapshot_status,
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
    database_included = False
    oauth_tokens_included = False
    env_snapshot_status = "redacted"

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        db_path = sqlite_database_path(active)
        if db_path and db_path.exists():
            temp_db = backups_dir / f"commsdesk-{stamp}.db"
            shutil.copy2(db_path, temp_db)
            archive.write(temp_db, arcname=db_path.name)
            included.append(db_path.name)
            database_included = True
            temp_db.unlink(missing_ok=True)
        archive.writestr(
            "config-snapshot.redacted.json",
            json.dumps(_redacted_config_snapshot(active), indent=2, sort_keys=True),
        )
        included.append("config-snapshot.redacted.json")
        env_example = PROJECT_ROOT / ".env.example"
        if env_example.exists():
            archive.write(env_example, arcname=".env.example")
            included.append(".env.example")
        if active.backup_include_env_file and (PROJECT_ROOT / ".env").exists():
            archive.write(PROJECT_ROOT / ".env", arcname=".env")
            included.append(".env")
            env_snapshot_status = "included"
        if active.backup_include_oauth_tokens:
            for token_file in (
                active.gmail_token_file,
                active.google_calendar_token_file,
                active.microsoft_graph_token_file,
            ):
                path = (
                    PROJECT_ROOT / token_file
                    if not Path(token_file).is_absolute()
                    else Path(token_file)
                ).resolve()
                if path.exists():
                    archive.write(path, arcname=path.name)
                    included.append(path.name)
                    oauth_tokens_included = True
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
        database_included=database_included,
        oauth_tokens_included=oauth_tokens_included,
        env_snapshot_status=env_snapshot_status,
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
        database_included=_zip_has_database(path),
        oauth_tokens_included=_zip_has_any(
            path,
            ("gmail_token.json", "google_calendar_token.json", "microsoft_graph_token.json"),
        ),
        env_snapshot_status="included" if _zip_has_any(path, (".env",)) else "redacted",
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
                database_included=_zip_has_database(path),
                oauth_tokens_included=_zip_has_any(
                    path,
                    ("gmail_token.json", "google_calendar_token.json", "microsoft_graph_token.json"),
                ),
                env_snapshot_status=(
                    "included" if _zip_has_any(path, (".env",)) else "redacted"
                ),
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


def _zip_has_database(path: Path) -> bool:
    return any(name.endswith(".db") or name.endswith(".sqlite") for name in _zip_names(path))


def _zip_has_any(path: Path, names: tuple[str, ...]) -> bool:
    present = set(_zip_names(path))
    return any(name in present for name in names)


def _redacted_config_snapshot(settings: Settings) -> dict[str, object]:
    data = settings.model_dump()
    redacted_markers = ("secret", "token", "password", "api_key", "client_secret")
    for key in list(data):
        if any(marker in key.lower() for marker in redacted_markers):
            data[key] = "[redacted]" if data[key] else None
    data["backup_include_oauth_tokens"] = settings.backup_include_oauth_tokens
    data["backup_include_env_file"] = settings.backup_include_env_file
    return data
