.PHONY: seed classify demo canary all
seed:
	python3 fixtures/seed.py
classify:
	python3 after/classification.py
demo:
	python3 harness/measure.py
canary:
	python3 -m pytest tests/ -q
all: seed classify demo canary html
html:
	python3 build_html.py
