# VELPO - dev tasks.  Works in Git Bash / WSL / macOS / Linux.
PY   ?= python
NPM  ?= npm
SRC  := algorithms model config.py curriculum.py engine.py explain.py api.py

.PHONY: setup test lint typecheck format benchmark ablation frontend serve api clean

setup:
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	cd frontend && $(NPM) install

test:
	$(PY) -m pytest --cov --cov-report=term-missing

lint:
	$(PY) -m ruff check $(SRC) tests benchmarks
	$(PY) -m ruff format --check $(SRC) tests benchmarks
	cd frontend && $(NPM) run lint

format:
	$(PY) -m ruff format $(SRC) tests benchmarks
	$(PY) -m ruff check --fix $(SRC) tests benchmarks

typecheck:
	$(PY) -m mypy

benchmark:
	$(PY) -m benchmarks.benchmark

ablation:
	$(PY) -m benchmarks.ablation_velocity

frontend:
	cd frontend && $(NPM) install && $(NPM) run build

serve: frontend
	$(PY) -m uvicorn api:app --port 8000

api:
	$(PY) -m uvicorn api:app --reload --port 8000

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage web frontend/dist frontend/node_modules *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
