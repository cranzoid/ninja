.PHONY: lint format typecheck test check

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy .

test:
	pytest

check: lint typecheck test
