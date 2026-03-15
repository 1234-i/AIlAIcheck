# Database Migrations (Alembic)

## Setup
- Alembic config: `alembic.ini`
- Migration env: `alembic/env.py`
- Revisions: `alembic/versions/`

The migration env reads `DATABASE_URL` from runtime settings (`app.core.config.Settings`).

## Common Commands
- Create a new migration from model changes:
```bash
alembic revision --autogenerate -m "describe change"
```

- Upgrade to latest:
```bash
alembic upgrade head
```

- Downgrade one revision:
```bash
alembic downgrade -1
```

- Show migration history:
```bash
alembic history
```

- Show current revision:
```bash
alembic current
```

## Recommended Local Flow
1. Ensure `.env` has a valid `DATABASE_URL`.
2. Run `alembic upgrade head`.
3. Apply model changes.
4. Run `alembic revision --autogenerate -m "..."`.
5. Review generated migration file manually.
6. Run `alembic upgrade head` and validate app/tests.
7. If needed, verify rollback with `alembic downgrade -1`.

## Notes
- Keep migrations deterministic and backward-safe.
- Never edit historical migrations already applied in shared environments.
- For breaking changes, include explicit data migration strategy in the revision message/body.
