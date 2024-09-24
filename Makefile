format:
	black src/*

check_format:
	black --check src/*

lint: 
	flake8 --verbose ./src

typecheck:
	mypy ./src/*