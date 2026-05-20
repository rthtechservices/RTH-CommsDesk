"""Phase 29 — Outlook write action types

Documents the addition of Outlook/Microsoft Graph write action types to
ExecutionActionType. SQLite stores enum values as VARCHAR; no column
DDL changes are required. This migration exists to keep the version
chain coherent and to document the Phase 29 intent.

Revision ID: 0018_outlook_write_action_types
Revises: 0017_app_stat_records
Create Date: 2026-05-20
"""

revision = "0018_outlook_write_action_types"
down_revision = "0017_app_stat_records"
branch_labels = None
depends_on = None

# New ExecutionActionType values added in Python (stored as VARCHAR in SQLite):
#   create_outlook_draft
#   send_outlook_reply
#   apply_outlook_mail_modify
#   create_outlook_calendar_event
#
# No DDL changes are needed for SQLite because enum columns are stored as
# VARCHAR and validated at the Python StrEnum layer. This migration acts as
# a documentation checkpoint and version-chain marker.


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
