# VELPO - thin wrapper over `python velpo.py` (which needs no make; works on Windows too).
PY ?= python

.PHONY: setup doctor demo test lint fmt benchmark ablation datasets api ui serve clean

setup:      ; $(PY) velpo.py setup
doctor:     ; $(PY) velpo.py doctor
demo:       ; $(PY) velpo.py demo
test:       ; $(PY) velpo.py test
lint:       ; $(PY) velpo.py lint
fmt:        ; $(PY) velpo.py fmt
benchmark:  ; $(PY) velpo.py benchmark
ablation:   ; $(PY) velpo.py ablation
datasets:   ; $(PY) velpo.py datasets
api:        ; $(PY) velpo.py api
ui:         ; $(PY) velpo.py ui
serve:      ; $(PY) velpo.py serve

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage web \
	       frontend/dist frontend/node_modules benchmarks/data/cache *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
