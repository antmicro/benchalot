.PHONY: format check_format lint typecheck sanitize tuttest unittest

format:
	black src/benchmarker/*
	black tests/*

check_format:
	black --check src/benchmarker/*
	black --check tests/*

# ignore errors related to max line length (80 characters) and errors related to placing new line characters before binary operators (black formatter does not solve them)
lint: 
	flake8 --verbose  --ignore=E501,W503 ./src
	flake8 --verbose  --ignore=E501,W503 ./tests

typecheck:
	mypy ./src/benchmarker/*.py

sanitize: format lint typecheck

tuttest:
	./.ci/tuttest.sh

unittest:
	python -m unittest discover tests
