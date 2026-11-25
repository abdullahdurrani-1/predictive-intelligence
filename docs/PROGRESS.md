# Progress Log

Read this first when resuming work.

## Current status — 2026-11-25

**All 14 phases have a delivered artefact.** The analysis (Phases 1–9) is complete and executed. The assistant, application, tests and deployment files (Phases 10–12) are built and tested locally. The paper and video script (Phases 13–14) are written from the actual results.

What is **not** done, stated plainly:

| Item | State |
|---|---|
| Assistant's language-model layer | The web application's assistant runs on Google Gemini and has been exercised live. The older Anthropic path used by the Streamlit dashboard has still never been run (no Anthropic key). |
| Docker | Removed at the owner's request on 2026-11-25 (D-019). |
| GitHub Actions workflow | Written (Python tests and front-end build); runs for the first time when the repository is pushed. |
| Video | Script and storyboard only. Nothing has been recorded. |
| Research paper | Complete draft in Markdown. Not typeset, not reviewed by anyone else. References 2, 3, 4 and 12 were checked online (2, 3 and 4 again on 2026-11-25: authors, venue, pages and DOI match). References 1 (the dataset paper, in `data/raw/`) and 5–11, 13 are standard works cited from their well-known records and have not been opened individually. |
| NASA scoring constants | Confirmed 2026-11-25 (D-020): 13 for early, 10 for late. No score changes. |
| Git | Repository initialised, nothing committed, at the owner's request. |

The owner asked on 2026-11-13 to carry on through all phases without stopping for approval at each milestone, and to leave Git commits until the end.

## Web application (3D engine interface)

Plan: [UI_ARCHITECTURE.md](UI_ARCHITECTURE.md). React + TypeScript + React Three Fiber in `frontend/`, talking to the FastAPI service. **All seven sections are built and read real data** (2026-11-13).

| Section | What it shows | Checked how |
|---|---|---|
| Engine Intelligence | 3D turbofan (view modes, cutaway, camera presets, pause, full screen), engine explorer, estimate and range, influences, history with flight slider | Headless browser; real figures for engines 37 and 54 |
| Sensor Intelligence | All 21 sensors with trend and model reliance, history of up to 4 sensors, compare with another engine, correlation map, reliance chart | Headless browser |
| AI Assistant | Chat per engine, suggestions, copy, evidence under each answer, "Explain like I'm new to aviation", language-model switch, maintenance briefing | Headless browser; a live Gemini answer passed the grounding check |
| Research Lab | Model comparison, actual vs predicted, learning curves, uncertainty, FD001–FD004 and transfer, tuning | Headless browser; every table comes from `experiments/` |
| Model Center | Served model, training and validation, measured performance, registry, limitations | Headless browser |
| Monitoring | Drift by sensor computed on request, simulated-fault switch, predictions served | Headless browser; alert appears when the fault is switched on |
| Settings | Assistant provider and key status, display options, data and model settings | Headless browser |

Assistant: Google Gemini through `google-genai`, with tools in `src/assistant/tools.py` and orchestration in `src/assistant/chat.py`. Key in `.env` (`GOOGLE_API_KEY`, not in Git). Default model `gemini-3.5-flash-lite`, backup `gemini-3.5-flash`; on 2026-11-13 the newer models on this key timed out or reported high demand. Override with `GEMINI_MODEL`.

Known gaps:

- **Answers are not streamed word by word.** They are checked against the evidence first and shown whole. Live answers took roughly 10 to 70 seconds in testing.
- **The grounding check covers numbers only.** A wrong statement without a number would pass. Only a handful of live answers have been read by hand.
- **Only FD001 engines can be opened.** FD002–FD004 appear as research results.
- **No 0–100 health score**, because no validated formula exists; the status bands are used instead.
- **The engine is a conceptual procedural model**, labelled as such. No licensed GLB asset.
- **Clicking the history chart to pick a flight is unverified**; the slider works.
- **Checked in a headless browser with software rendering only.** Nobody has judged the look and smoothness on a real GPU, and there are no automated front-end tests.
- **Bundle is about 5.7 MB**, not code-split (Plotly and Three.js are most of it); the first load is slow on a poor connection.

Run it: `uvicorn api.main:app` in one terminal, `cd frontend; npm install; npm run dev` in another, then open http://localhost:5173 (use `localhost`, not `127.0.0.1`).

## Finalisation — 2026-11-25

- **Docker removed** at the owner's request (D-019): `Dockerfile`, `docker-compose.yml`, `.dockerignore` deleted; the CI workflow now runs the Python tests and the front-end type-check and build.
- **NASA scoring constants confirmed** (D-020). No numbers change.
- **Test report** (`scripts/test_report.py` → `reports/FD001_test_report.pdf`, 4 pages): the served model on the 100 official FD001 test engines. It reproduces the stored results exactly: RMSE 15.107, MAE 10.837, NASA score 321.865, 95 of 100 engines inside their range (3 failed sooner, 2 lasted longer), 54 late estimates (7 by more than 20), MAE 3.3 on the 25 engines with 30 or fewer flights left, no false end-of-life alarms. Its average range width is 44.4 flights against 44.3 in notebook 09, because the served range is also stretched where needed to contain the estimate.
- **PDF layout checked by eye** (pages rendered to images): the engine report's "Something to consider" heading no longer separates from its text, and its opening note no longer repeats itself.
- **Assistant:** a greeting in front of a question ("hi, is this engine healthy?") is now dropped before the question is answered, so the question gets a normal, evidence-based answer.

## Upload, data checks and end-to-end test — 2026-11-16

- **Data checks before the model** (`src/service/validation.py`): refuses data whose flight settings or typical sensor values are far outside the training data (different units, different engine type, another flight condition); warns when a sensor the model uses has stopped changing or has isolated extreme readings. No demonstration or training engine triggers a refusal or a warning.
- **Upload** (`api/uploads.py`, "Upload Engine Data" page): CSV with a header, or the NASA text layout; a multi-engine file asks which engine; the file is not stored. Uploaded engines are shown on the upload page only; they cannot be opened in the 3D screen or asked about in the assistant.
- **End-to-end check** (`scripts/end_to_end_check.py`, results in `experiments/end_to_end_check.csv`): 280 upload files built from the 100 unseen NASA test engines at three points in their lives.

| Case | Files | Median miss (flights) | Truth inside range |
|---|---:|---:|---:|
| As recorded | 100 | 7.5 | 97% |
| 20 flights earlier | 92 | 14.0 | 95.7% |
| 40 flights earlier | 88 | 18.0 | 92.0% |

  Near failure (30 or fewer flights left, 32 files): median miss 3; 75% rated "near end of predicted life". No healthy engine (more than 100 flights left, 129 files) was rated near end of life. Nine files failed sooner than their range. All ten broken-file cases are now handled (refused, or answered with a warning). Nine live assistant questions passed their checks.
- **Paper audit** (2026-11-16): 93 numbers in `research-paper/paper.md` checked against the result files and notebook outputs, zero mismatches; RMSE, MAE and NASA score recomputed independently from saved predictions and matched.
- **User guide** for non-technical users: [USER_GUIDE.md](USER_GUIDE.md).
- Tests: 42 passing.

Still open from this round: the stuck-sensor check only catches a sensor that is nearly flat for 30 flights, not one that drifts or reads with a constant offset; the range margin for "implausible" values (half the training range) is a judgement, not a tuned value; Excel files are not accepted.

## Report download, assistant small talk and new theme — 2026-11-16

- **Report download** (`src/service/report.py`): a PDF per engine (status, estimate, range, chart, influences, suggestion, limits), generated with ReportLab from the same fact sheet as the screens. `GET /engines/{id}/report?cycle=` for demonstration engines; uploads return a report when sent with `as_report`. Buttons on the engine screen, the upload page and the assistant's briefing.
- **Assistant small talk** (`src/assistant/chat.py`): greetings, thanks and "who are you" get a short conversational reply with no lookups. A real question answered without lookups is retried once, then falls back to the rule-based answer. Known weak spot: a greeting and a question in one message ("hi, is this engine healthy?") still ends in the rule-based answer with the default Gemini model.
- **Theme**: warm black background, white text, orange accent, burgundy navigation, at the owner's request. Sage green is kept for "no wear" and "raised the estimate" so those stay distinct from the orange accent. Checked on the engine screen only; the other pages use the same variables but were not individually reviewed after the change.
- Tests: 59 passing.

## Headline results

FD001 test set, 100 engines, truth as supplied, predictions limited to 0–125. ± is the spread over seeds.

| Model | Trained on | Test RMSE | Test NASA score |
|---|---|---:|---:|
| Predict the average | 100 engines | 43.1 | 33,629 |
| Linear Regression | 100 engines | 18.0 | 511 |
| Random Forest (5 seeds) | 100 engines | 13.85 ± 0.06 | 265 |
| XGBoost, default (5 seeds) — the served model | 100 engines | 14.78 ± 0.29 | 305 |
| XGBoost, tuned (5 seeds) | 100 engines | 14.42 ± 0.12 | 296 |
| MLP / GRU / TCN / LSTM, 3-seed ensembles | 80 engines | 15.8 / 16.0 / 16.3 / 16.4 | 344 to 387 |

All four subsets, XGBoost with the same untuned recipe (15 common sensors, regime normalisation):

| Subset | CV RMSE | Test RMSE | Test RMSE, truth capped at 125 | 90% range coverage |
|---|---:|---:|---:|---:|
| FD001 | 13.3 | 14.9 | 13.8 | 95.0% |
| FD002 | 14.2 | 25.0 | 12.8 | 91.5% |
| FD003 | 12.3 | 15.5 | 14.0 | 89.0% |
| FD004 | 14.4 | 26.4 | 14.3 | 87.1% |

Main findings:

1. Validating on random rows instead of whole engines understated error by 34% (notebook 04).
2. Each sensor's change from the engine's own early-life level is the feature that matters: removing it costs 3.7 cycles; removing any other group costs under 0.4 (notebook 07).
3. Deep learning did not beat tree models on FD001. The networks looked better on the hold-out engines and worse on the test set (notebook 06). On FD002–FD004 no architecture won consistently and the Transformer was best on none (notebook 10).
4. Tuning with Optuna gained about 0.36 cycles (notebook 07).
5. A sensor frozen at a healthy value makes the model silently more optimistic; with S11 frozen, engines late by more than 20 cycles rose from 7 to 24 (notebook 07).
6. SHAP: S11 (Ps30), S4, S12 lead; top sensors are stable across retrained models, the detailed order is not (notebook 08).
7. 90% ranges covered 95 of 100 FD001 test engines; 3 of the 5 misses failed sooner than the range. Near-failure coverage falls to 76% on FD004 (notebooks 09, 10).
8. An unseen fault mode hurts a transferred model far more than an unseen flight condition (notebook 10).

Result files: `experiments/*.csv`, `experiments/fd001_uncertainty.json`, `experiments/fd001_xgboost_tuned_params.json`.

## What exists

| Phase | Deliverable | Verified how |
|---|---|---|
| 1 | Structure, `.venv`, pinned requirements, Git, docs | Environment loads FD001 |
| 2–3 | Notebooks 01, 02, 03 | Executed, no error cells |
| 4 | Notebook 04; `src/features`, `src/data/splits.py`, `src/config.py` | Executed; causality test passes |
| 5 | Notebook 05 | Executed; retraining script reproduces 15.107 |
| 6 | Notebook 06; `src/models/networks.py`, `training.py` | Executed (16 networks cached in `models/deep/`) |
| 7 | Notebook 08; `src/explainability` | Executed; additivity checked to 0.0003 cycles |
| 8 | Notebook 09; `src/models/uncertainty.py` | Executed |
| 9 | Notebooks 07 and 10; MLflow log; `src/features/regimes.py`, `src/data/prepare.py` | Executed (20 networks cached in `models/deep_generalisation/`) |
| 10 | `src/assistant/`, `src/service/engine_service.py` | Unit tests; rule-based layer exercised on real engines |
| 11 | `api/main.py`, `dashboard/app.py` | API tests pass; dashboard run headlessly against the live API with no exceptions |
| 12 | `tests/`, `scripts/train.py`, `simulate_stream.py`, `monitor_report.py`, CI workflow | 36 tests pass; scripts run; CI not yet run (Docker later removed, D-019) |
| 13 | `research-paper/paper.md` | Numbers taken from notebook outputs |
| 14 | `video-documentation/VIDEO_SCRIPT.md` | Numbers taken from notebook outputs |

Decisions D-001 to D-018 are in [DECISIONS.md](DECISIONS.md). Design is in [ARCHITECTURE.md](ARCHITECTURE.md).

## How to re-run

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q
python -m jupyter nbconvert --to notebook --execute --inplace notebooks\<name>.ipynb
python scripts/train.py --no-promote        # retrain and register without replacing the served models
uvicorn api.main:app                        # then: streamlit run dashboard/app.py
```

Long-running notebooks reuse saved work: 06 and 10 reload trained networks (set `RETRAIN = True` inside to retrain; about 30 and 60 minutes on CPU), and 07 reuses its Optuna search from `experiments/optuna_fd001.db` (delete that file to search again; about 19 minutes).

## Open items

1. ~~NASA scoring constants~~ — resolved 2026-11-25, see D-020.
2. **Run the language-model layer.** Set `ANTHROPIC_API_KEY`, start the API, ask questions in the dashboard, and confirm the answer source reads "language model (grounding check passed)". Review a sample of answers by hand: the grounding check catches invented numbers, not invented statements without numbers.
3. **Push and watch CI.** The workflow has not run yet.
4. **Sensor and setting names are inferred** from the order of Table 2 in the NASA paper; the dataset README only numbers them.
5. **Near-failure coverage of the ranges** is below target on FD002 and FD004. Calibrating by predicted RUL is the suggested fix; not done.
6. **Neural networks on FD002–FD004** have one seed for GRU and Transformer and no tuning. The comparison there is indicative only.
7. **References 5–11 and 13** are standard works cited from their well-known records; open them individually before formal submission.
8. **Notebook numbering:** 07 was built after 08 and 09 because it covers Phase 9; 10 was added for generalisation.
9. **First Git commit** when the owner is ready.

## Dependency changes

| Date | Change |
|---|---|
| 2026-11-13 | Initial set: numpy, pandas, matplotlib, seaborn, plotly, scikit-learn, jupyterlab, ipykernel |
| 2026-11-13 | Phase 5: xgboost; scipy and joblib pinned |
| 2026-11-13 | Phase 6: torch 2.15.0 CPU build |
| 2026-11-13 | Phase 7: shap |
| 2026-11-13 | Phase 9: optuna, mlflow |
| 2026-11-13 | Phases 10–12: anthropic, fastapi, uvicorn, streamlit, httpx, pytest; `requirements-serve.txt` added for the container |
