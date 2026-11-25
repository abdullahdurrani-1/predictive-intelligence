# Project Plan — Predictive Intelligence

An end-to-end AI system for aircraft engine health, failure prediction, and decision support, built on the NASA C-MAPSS benchmark.

**Goal:** turn engine sensor data into an estimate of Remaining Useful Life (RUL), explain that estimate, state how reliable it is, and communicate it in language a maintenance manager can act on.

**Boundary:** this is a research and demonstration system on simulated data. It never presents C-MAPSS as real aircraft telemetry, and its outputs are decision support, not maintenance authorisation.

---

## How the work is organised

- Work proceeds in numbered phases. Each phase ends at a **checkpoint**: the work is shown, verified, and approved before the next phase starts.
- FD001 comes first. FD002–FD004 are used only after the full pipeline works on FD001.
- The test set is touched once per model, for final evaluation. All tuning uses engine-wise validation splits of the training set.
- Every preprocessing and modelling choice is recorded in [DECISIONS.md](DECISIONS.md). Status is tracked in [PROGRESS.md](PROGRESS.md).
- Dependencies and folders are added when a phase needs them, not in advance.

---

## Roadmap

| # | Phase | Main deliverable | Done when |
|---:|---|---|---|
| 1 | Environment and foundation | Repo structure, virtual environment, Git, core docs | A fresh clone plus the documented setup steps gives a working environment |
| 2 | Data understanding and statistics | `01_dataset_understanding.ipynb`, `03_statistical_analysis.ipynb` | Structure, missing values, constant sensors, lifetimes, and correlations are measured and explained |
| 3 | EDA and visual storytelling | `02_exploratory_data_analysis.ipynb`, shared plot theme | Sensor trends and degradation trajectories are shown, including a justified 3D view |
| 4 | Data preparation and features | `04_feature_engineering.ipynb`, `src/data`, `src/features` | RUL target, scaling, sensor selection, sliding windows, and engine-wise splits are reproducible and leak-free |
| 5 | Traditional ML baselines | `05_machine_learning.ipynb` | Linear Regression, Random Forest, XGBoost compared on RMSE, MAE, NASA score |
| 6 | Deep learning | `06_deep_learning.ipynb`, `src/models` | MLP, LSTM, GRU, TCN (Transformer only if justified) compared on the same splits |
| 7 | Explainable AI | `08_explainable_ai.ipynb` | SHAP-based sensor attributions, checked for plausibility, with causation caveats |
| 8 | Uncertainty | `09_uncertainty_analysis.ipynb` | Prediction intervals with measured coverage and width |
| 9 | Evaluation and experiments | `07_model_evaluation.ipynb`, MLflow runs | Ablations, tuning, error analysis, and FD002–FD004 generalisation |
| 10 | Question-answering assistant | `src/assistant` | Plain-English answers grounded only in real predictions, attributions, and intervals |
| 11 | Application and dashboard | `api/`, `dashboard/` | Engine selection, health view, RUL with uncertainty, explanations, and the assistant in one app |
| 12 | MLOps and deployment | CI, monitoring (Docker removed, D-019) | Tested API, containerised, with drift and prediction monitoring demonstrated |
| 13 | Research paper | `research-paper/` | Paper written from actual results with verified citations |
| 14 | Video documentation | `video-documentation/` | Script and storyboard based on the real system |

Notebook numbers follow the target structure in the master brief; the build order is the phase order above.

---

## Milestone 1 — Environment and project foundation

**In simple terms:** before analysing any engine, we set up the workshop. A mechanic does not start an overhaul on a cluttered bench with unlabelled parts; they lay out the tools, tag the parts, and open a logbook. Milestone 1 is that step for this project.

What it involves and why:

| Step | Why it matters |
|---|---|
| Put the NASA files in `data/raw/`, mark them read-only, record their checksums | The raw data is our evidence. If it changes silently, every later result is in doubt. |
| Create a project virtual environment with pinned package versions | The same code can give different numbers under different library versions. Pinning makes results repeatable on any machine. |
| Initialise Git with a `.gitignore` | Git is the project's history. The ignore file keeps large data, secrets, and generated files out of that history. |
| Write the README, plan, progress log, and decision log | So the project can be resumed, reviewed, and defended later. |

**How to verify it:** see the checklist in [PROGRESS.md](PROGRESS.md).

## Milestone 2 preview — first notebook

`notebooks/01_dataset_understanding.ipynb` on FD001: load the three files with named columns, confirm the shapes, look at how long engines live, find constant and near-constant sensors, and compute the RUL label for the training set. No modelling.
