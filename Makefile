.PHONY: format check_format lint typecheck sanitize tuttest

format:
	black src/*

check_format:
	black --check src/*
# ignore errors related to max line length (80 characters) and errors related to placing new line characters before binary operators (black formatter does not solve them)
lint: 
	flake8 --verbose  --ignore=E501,W503 ./src

typecheck:
	mypy ./src/main.py ./src/validation.py ./src/preparation.py  ./src/execution.py ./src/output.py

sanitize: format lint typecheck
tuttest:
	tuttest README.md config.yml > config.yml
	tuttest README.md install | bash 
	tuttest README.md run | bash
	[ -f plot.png ]
	[ -f result.csv ]
	[ -f table.md ]
	printf "  cs2:\n    filename: \"result2.csv\" \n    format: \"csv\"" >> config.yml
	tuttest README.md update-output | bash
	[ -f result2.csv ]
	rm result2.csv
	tuttest README.md update-output-csv | bash
	[ -f result2.csv ]
