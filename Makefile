.PHONY: install test demo clean

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest -q

demo:
	python examples/run_demo.py

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache *.egg-info build dist
