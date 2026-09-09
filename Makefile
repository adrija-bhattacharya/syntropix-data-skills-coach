# VELPO - dev tasks.  Works in Git Bash / WSL / macOS / Linux.
PY  ?= python
NPM ?= npm

.PHONY: setup test lint typecheck format benchmark frontend serve api clean

setup:
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	cd frontend && $(NPM) install

test:
	$(PY) -m pytest --cov=velpo --cov-report=term-missing

lint:
	$(PY) -m ruff check velpo tests benchmarks
	$(PY) -m ruff format --check velpo tests benchmarks
	cd frontend && $(NPM) run lint

format:
	$(PY) -m ruff format velpo tests benchmarks
	$(PY) -m ruff check --fix velpo tests benchmarks

typecheck:
	$(PY) -m mypy

benchmark:
	$(PY) -m benchmarks.benchmark

frontend:
	cd frontend && $(NPM) install && $(NPM) run build

serve: frontend
	$(PY) -m uvicorn velpo.api:app --port 8000

api:
	$(PY) -m uvicorn velpo.api:app --reload --port 8000

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage velpo/web frontend/dist frontend/node_modules
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
