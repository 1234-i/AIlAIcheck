PYTHON ?= python3
PIP_INDEX_URL ?= https://pypi.org/simple

.PHONY: install install-dev run worker test test-unit test-integration lint compile-check demo mvp-demo build-golden eval-golden seed-rules migrate upgrade downgrade stage-release-check

install:
	$(PYTHON) -m pip install -i $(PIP_INDEX_URL) -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -i $(PIP_INDEX_URL) -r requirements-dev.txt

run:
	uvicorn app.main:app --reload

worker:
	celery -A app.tasks.celery_app worker --loglevel=info

test:
	LLM_MODE=mock pytest -q

test-unit:
	LLM_MODE=mock pytest tests/unit -q

test-integration:
	LLM_MODE=mock pytest tests/integration -q

lint:
	ruff check app tests scripts

compile-check:
	$(PYTHON) -m compileall app tests scripts

demo:
	PYTHONPATH=. LLM_MODE=mock $(PYTHON) scripts/demo_run.py

mvp-demo:
	PYTHONPATH=. LLM_MODE=mock $(PYTHON) scripts/run_mvp_closed_loop.py

build-golden:
	PYTHONPATH=. $(PYTHON) scripts/build_golden_dataset.py

eval-golden:
	PYTHONPATH=. $(PYTHON) scripts/evaluate_golden.py

seed-rules:
	PYTHONPATH=. $(PYTHON) scripts/seed_rules.py

migrate:
	alembic revision --autogenerate -m "auto migration"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

stage-release-check:
	PYTHONPATH=. $(PYTHON) scripts/stage_release_check.py --manifest stage_release_manifest.json --strict
