.PHONY: all data sim fit backtest app test clean run-api

all: data sim fit backtest

data:
	python -m ews.ingest.weather

sim:
	python -m ews.sim.generate

fit:
	python -m ews.models.fit

backtest:
	python -m ews.validation.backtest

app:
	python -m streamlit run app/Home.py

run-api:
	python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v

clean:
	python -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) for p in ['__pycache__', '.pytest_cache', 'ews/__pycache__', 'ews/*/__pycache__']]"
