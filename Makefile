.PHONY: format check_format lint typecheck sanitize tuttest

format:
	black src/benchmarker/*

check_format:
	black --check src/benchmarker/*
# ignore errors related to max line length (80 characters) and errors related to placing new line characters before binary operators (black formatter does not solve them)
lint: 
	flake8 --verbose  --ignore=E501,W503 ./src

typecheck:
	mypy ./src/benchmarker/*.py

sanitize: format lint typecheck

tuttest:
	./.ci/tuttest.sh
