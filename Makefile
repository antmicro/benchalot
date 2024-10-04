.PHONY: format check_format lint typecheck sanitize tuttest

format:
	black src/*

check_format:
	black --check src/*
# ignore errors related to max line length (80 characters) and errors related to placing new line characters before binary operators (black formatter does not solve them)
lint: 
	flake8 --verbose  --ignore=E501,W503 ./src

typecheck:
	mypy ./src/main.py ./src/validation.py ./src/preparation.py  ./src/execution.py ./src/output.py ./src/variance.py ./src/log.py

sanitize: format lint typecheck

TMP_OUT_DIR := $(shell mktemp -d)
TMP_CONFIG := $(shell mktemp)
tuttest:
	tuttest README.md config.yml | sed -e 's|filename: "|filename: "$(TMP_OUT_DIR)/|' > $(TMP_CONFIG)
ifdef ($(CI))
	tuttest README.md dependencies | bash 
endif
	tuttest README.md install | bash 
	tuttest README.md run | sed -e 's|config.yml|$(TMP_CONFIG)|' | bash
	[ -f $(TMP_OUT_DIR)/plot.png ]
	[ -f $(TMP_OUT_DIR)/result.csv ]
	[ -f $(TMP_OUT_DIR)/table.md ]