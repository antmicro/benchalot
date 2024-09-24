format:
	black src/*

check_format:
	black --check src/*

lint: 
	flake8 --verbose  --ignore=E501 ./src

typecheck:
	mypy ./src/*

sanatize: format lint typecheck