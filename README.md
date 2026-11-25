# Predictive Intelligence

An end-to-end AI system for aircraft engine health monitoring. It estimates an engine's Remaining Useful Life (RUL) from sensor data, attaches a range that has been checked against unseen engines, shows which measurements drove the estimate, and explains all of it in plain language.

> **Research and demonstration project.** It uses the NASA C-MAPSS dataset, which is simulated turbofan data, not telemetry from real aircraft. Its outputs are estimates for study and decision support. They are not maintenance instructions and cannot replace approved aviation maintenance procedures.

## What it does

- **Estimates remaining life** in flights, with a 90% range.
- **Explains the estimate**: which sensors moved it and in which direction.
- **Answers questions in ordinary English**, using only what the model actually found.
- **Monitors itself**: logs predictions and flags incoming data that no longer resembles the training data.

## Results in brief (FD001 test set, 100 engines)

| Model | Test RMSE (flights) | Test NASA score |
|---|---:|---:|
| Random Forest | 13.85 ± 0.06 | 265 |
| XGBoost, tuned | 14.42 ± 0.12 | 296 |
| XGBoost, default (served) | 14.78 ± 0.29 | 305 |
| MLP / GRU / TCN / LSTM, 3-seed ensembles | 15.8 to 16.4 | 344 to 387 |
| Linear Regression | 18.0 | 511 |

± is the spread over five random seeds. Lower is better for both columns. The one saved model the application serves scores RMSE 15.11 and NASA score 322 (see the [test report](reports/FD001_test_report.pdf)); the table gives the five-seed average.

- Tree models on engineered features matched or beat the neural networks on this subset.
- One feature idea, each sensor's change from the engine's own early-life level, accounts for most of the accuracy.
- The 90% prediction range contained the truth for 95 of 100 test engines.
- Full numbers, including the other three subsets: [docs/PROGRESS.md](docs/PROGRESS.md) and the notebooks.

## Setup

Requires Python 3.13. From the project root, in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

Then obtain the data as described in [data/README.md](data/README.md) and verify it against `data/checksums.sha256`.

In VS Code, choose `.venv` as the Python interpreter and as the notebook kernel.

## Running it

Train the served models (about two minutes), or run the notebooks in order, which produce the same files:

```powershell
python scripts/train.py
```

Start the API, then the web application, in two terminals (Node.js 20 or later is needed for the second):

```powershell
uvicorn api.main:app                          # http://127.0.0.1:8000/docs
cd frontend; npm install; npm run dev         # http://localhost:5173
```

The web application has eight sections: Engine Intelligence (3D engine), Sensor Intelligence, AI Assistant, Research Lab, Model Center, Monitoring, Upload Engine Data and Settings. Every section reads real results from the API; nothing is placeholder data. Design: [docs/UI_ARCHITECTURE.md](docs/UI_ARCHITECTURE.md). The earlier Streamlit dashboard still works: `streamlit run dashboard/app.py`.

Other commands:

```powershell
python -m pytest -q                                   # tests
python scripts/end_to_end_check.py --assistant        # test the running system on unseen engines and bad files
python scripts/test_report.py                         # PDF of the served model on NASA's 100 test engines
python scripts/simulate_stream.py --engine 37         # replay an engine flight by flight through the API
python scripts/monitor_report.py                      # drift and prediction report
python scripts/monitor_report.py --inject-drift       # the same, with a simulated sensor fault
mlflow ui --backend-store-uri sqlite:///mlflow.db     # browse logged experiments
```

### The assistant and the language model

The assistant works without any API key: a built-in rule-based layer answers common questions directly from the model's results. To have Google Gemini write the answers, create a file called `.env` in the project root containing `GOOGLE_API_KEY=your-key` (the file is ignored by Git and must never be committed), then start the API. Gemini looks up the engine's results through tools; every answer is checked against that evidence and discarded if it states a number that is not there. (The older Streamlit dashboard uses `ANTHROPIC_API_KEY` instead.)

### Test report

[reports/FD001_test_report.pdf](reports/FD001_test_report.pdf) shows the served model on NASA's 100 official FD001 test engines, which were never used for training, tuning or calibration: the headline measures, a chart of estimate against truth, and every engine's estimate, range and error. `python scripts/test_report.py` rebuilds it from the raw files.

## Repository layout

```text
data/                raw NASA files (read-only, not in Git), checksums, data notes
docs/                plan, progress log, decision log, architecture, dataset inventory
notebooks/           01-10: the full analysis, in order
src/
  config.py          settings decided in Phase 4
  data/              loading, engine-wise splitting, one preparation recipe for all subsets
  features/          RUL cap, rolling and baseline features, windows, flight-condition scaling
  models/            neural networks, training loop, prediction ranges
  evaluation/        RMSE, MAE, NASA score
  explainability/    SHAP helpers
  service/           builds the fact sheet for an engine
  assistant/         plain-language answers
  monitoring/        drift statistics
  visualization/     shared figure style
api/                 FastAPI service
dashboard/           Streamlit dashboard (earlier interface, still working)
frontend/            React + Three.js web application (3D engine interface)
scripts/             retraining, test report, end-to-end check, streaming simulation, monitoring report
reports/             FD001 test report (PDF)
tests/               pytest suite
experiments/         result tables produced by the notebooks
models/              trained models (not in Git; rebuilt by scripts/train.py or the notebooks)
research-paper/      paper draft based on these results
video-documentation/ script and storyboard for the walkthrough
```

## Notebooks

| # | Notebook | Question it answers |
|---:|---|---|
| 01 | Dataset understanding | What is in the data, and is it clean? |
| 02 | Exploratory data analysis | What does wear look like across the fleet? |
| 03 | Statistical analysis | How early can wear be told apart from noise? |
| 04 | Feature engineering | How do we validate honestly, and which features help? |
| 05 | Machine learning | How good are Linear Regression, Random Forest and XGBoost? |
| 06 | Deep learning | Do MLP, LSTM, GRU and TCN do better? |
| 07 | Model evaluation | How much do results move with seeds, tuning, noise and sensor faults? |
| 08 | Explainable AI | Which sensors does the model rely on, and is that sensible? |
| 09 | Uncertainty | How wide is the range, and how often is it right? |
| 10 | Generalisation | Does it work on the other three subsets, and across them? |

Every notebook explains each step before the code and interprets each result after it.

## Using the application

A plain-English guide for people who are not engineers or programmers: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## How decisions were made

Every methodological choice is recorded with its evidence and its trade-off in [docs/DECISIONS.md](docs/DECISIONS.md). The design is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Limitations

- Simulated data from one engine model. Nothing here has been validated on real engines.
- The model cannot predict more than 125 flights; beyond that it reports "at least".
- A sensor frozen at a healthy value makes the model more optimistic. A completely flat sensor is flagged; one that drifts slowly is not.
- Only FD001 engines are served in the application. FD002 to FD004 are studied in notebook 10.
- The status labels and suggested actions are project conventions, not aviation standards.

## Dataset

A. Saxena, K. Goebel, D. Simon, and N. Eklund, "Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation," Proceedings of the 1st International Conference on Prognostics and Health Management (PHM08), Denver, CO, 2008.

## Licence

Code: MIT, see [LICENSE](LICENSE). The NASA C-MAPSS data is not included; obtain it as described in [data/README.md](data/README.md).
