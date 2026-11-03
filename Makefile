# Credit risk cut-off strategy · common commands
# First time:  make setup   (needs uv; on macOS also `brew install libomp` for LightGBM)
PY := .venv/bin/python

.PHONY: setup all sql notebooks export report app screenshots qa test sql-check clean

setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

all:            ## full pipeline: SQL features + data-quality checks -> notebooks -> HTML exports -> report
	$(PY) run.py

sql:            ## build DuckDB feature tables and data-quality tables only
	$(PY) run.py --stage sql

notebooks:      ## execute the four analysis notebooks in order
	$(PY) run.py --stage notebooks

export:         ## export executed notebooks to reports/*.html
	$(PY) run.py --stage export

report:         ## build reports/report.html and README figures
	$(PY) run.py --stage report

app:            ## launch the Streamlit demo app
	$(PY) -m streamlit run dashboard/app.py

screenshots:    ## capture each dashboard page to reports/figures/ (needs: $(PY) -m playwright install chromium)
	$(PY) scripts/screenshot_dashboard.py

qa:             ## click through every dashboard page, tab and option; fails on any error
	$(PY) scripts/qa_dashboard.py

test:           ## unit tests for the cost and policy formulas
	$(PY) -m pytest -q tests

sql-check:      ## run every SQL file on its own to prove each one executes independently
	$(PY) scripts/check_sql_files.py

clean:          ## remove local outputs (raw data is never touched)
	rm -rf data artifacts
