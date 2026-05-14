# AGENTS.md

## Project

This repository contains RTH CommsDesk, a personal communications triage system.

The application helps classify incoming communications, identify important contacts, suppress noise, and generate draft-only responses. It must prioritize privacy, safety, maintainability, and auditability.

## Non-negotiable rules

- Do not commit secrets, tokens, OAuth credentials, private messages, exported inbox data, or personal contact data.
- Do not implement auto-send functionality unless explicitly requested in a future task.
- Do not scrape private messaging platforms.
- Do not bypass platform terms, login protections, or API restrictions.
- Default to metadata/snippet storage, not full body storage.
- Make full message body ingestion opt-in.
- Redact private content from logs.
- Keep connectors modular.
- Keep AI providers swappable.
- Prefer deterministic logic before AI logic where practical.
- All generated drafts must remain drafts until manually approved.

## Development commands

Use the commands in README.md. Keep README.md current whenever setup, run, migration, or test commands change.

## Architecture expectations

Use:
- Python
- FastAPI
- SQLAlchemy
- Alembic
- pytest
- Pydantic settings

Main flow:

Source connector → normalized message model → classification → attention scoring → dashboard → user feedback.

## Coding style

- Keep services small and testable.
- Avoid giant files.
- Use type hints.
- Add tests for scoring/classification logic.
- Do not introduce cloud dependencies unless there is a local fallback.
- Do not make paid AI credentials mandatory for local development.

## MVP scope

The first MVP is Gmail-only and read-only.

Future channels should be represented by interfaces/stubs:
- Outlook/Microsoft Graph
- Teams
- Android notification bridge
- SMS
- WhatsApp
- Facebook Messenger

## Privacy posture

Assume all message content is sensitive. Store the minimum amount needed to generate the attention queue. Prefer summaries, snippets, classifications, and metadata over full raw content.
