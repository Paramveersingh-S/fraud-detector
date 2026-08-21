.PHONY: install lint typecheck test test-contract run-api run-consumer run-dashboard

install:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest tests/unit tests/integration -v

test-contract:
	pytest tests/contract -v

run-api:
	uvicorn fraud_spike.serving.api:app --reload --port 8000

run-consumer:
	python -m fraud_spike.streaming.consumer

run-dashboard:
	streamlit run src/fraud_spike/dashboard/app.py
