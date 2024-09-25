format:
	black src/*

check_format:
	black --check src/*
# ignore errors related to max line length (80 characters) and errors related to placing new line characters before binary operators (black formatter does not solve them)
lint: 
	flake8 --verbose  --ignore=E501,W503 ./src

typecheck:
	mypy ./src/*

sanitize: format lint typecheck