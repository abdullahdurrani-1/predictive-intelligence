# Decision Log

Each entry records what was decided, why, and what was given up. Add new entries at the bottom; do not rewrite old ones — supersede them with a new entry.

---

## D-001 — Raw data lives in `data/raw/`, read-only, with checksums
**Date:** 2026-11-13 · **Phase:** 1

**Decision:** All original NASA files sit in `data/raw/`, carry the read-only attribute, and have SHA-256 fingerprints in `data/checksums.sha256`.

**Why:** Every result in this project traces back to these files. A fixed location keeps notebook paths stable, and the checksums let anyone prove the data was not altered.

**Trade-off:** Deleting or replacing a raw file now needs a deliberate extra step.

## D-002 — Raw data is not committed to Git
**Date:** 2026-11-13 · **Phase:** 1

**Decision:** `data/raw/` and `data/processed/` are in `.gitignore`. Git tracks `data/README.md` and the checksum file instead.

**Why:** Git is designed for text that changes line by line, not for ~57 MB of static data. The data is publicly available from NASA and can be verified after download. DVC is planned for Phase 9 if dataset versioning is needed.

**Trade-off:** A fresh clone needs one manual download step.

## D-003 — Project virtual environment, pinned versions, dependencies added per phase
**Date:** 2026-11-13 · **Phase:** 1

**Decision:** The project uses its own `.venv` on Python 3.13. `requirements.txt` pins exact versions and currently lists only what Phases 1–3 need. Heavier libraries (XGBoost, PyTorch, SHAP, MLflow, FastAPI and others) are added in the phase that first uses them.

**Why:** The packages were previously installed globally, where another project can change them. Pinning makes results repeatable. Installing late avoids resolving version conflicts for tools we may configure differently by then.

**Trade-off:** `requirements.txt` changes several times during the project; each change is logged in PROGRESS.md.

## D-004 — FD001 first, other subsets later
**Date:** 2026-11-13 · **Phase:** 1

**Decision:** The whole pipeline is built and validated on FD001 before FD002–FD004 are touched.

**Why:** FD001 has one operating condition and one fault mode, so sensor changes reflect wear alone. That makes mistakes in the pipeline easier to see. The other subsets then become a genuine generalisation test.

**Trade-off:** Some design choices (for example dropping constant sensors) will need revisiting for the multi-condition subsets.

## D-005 — Where the README and the files disagree, the files win
**Date:** 2026-11-13 · **Phase:** 1

**Decision:** Measured facts from the data files override the dataset README.

**Why:** The README swaps the FD004 train/test engine counts and mislabels column 26. The files are internally consistent (the RUL file length matches the test engine count). Details in DATASET_INVENTORY.md, section 7.

## D-006 — Validation is always by whole engine
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebook 04, section 2

**Decision:** Model comparisons use 5-fold cross-validation grouped by engine. A fixed hold-out of 20 engines (seed 42) is used where a single validation set is needed, such as early stopping.

**Why:** Rows from one engine are near-duplicates of their neighbours. With history features, random-row validation reported an RMSE of 8.9 where the engine-wise figure was 13.5, understating error by 34%.

**Trade-off:** Only 100 engines, so each fold validates on 20 and fold-to-fold spread is noticeable. Differences smaller than that spread are not treated as real.

## D-007 — Columns dropped for FD001
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebooks 01 and 04

**Decision:** Drop the three operational settings, sensors 1, 5, 10, 16, 18, 19 (constant) and sensor 6 (two values). Do not use `cycle` as a feature. Keep sensors 9 and 14.

**Why:** Constant columns carry no information. Engine age predicts the fleet average, not the engine's condition. Removing sensors 9 and 14 raised validation error (21.7 to 24.0 on raw sensors; 15.2 to 16.5 with engineered features), despite their inconsistent direction across engines.

**Trade-off:** FD001-specific. The settings and several of these sensors vary in FD002 and FD004 and must be revisited there.

## D-008 — RUL label capped at 125
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebook 03 section 5, notebook 04 section 5

**Decision:** Training labels are min(RUL, 125).

**Why:** Without a cap, validation RMSE within 150 cycles of failure was about 33; with caps of 115 to 130 it was about 22.5 (fold spread about 1.2). A cap of 100 was worse (24.5). 125 lies in the flat best region, matches the point beyond which wear is statistically hard to detect, and is the most common value in the literature, which keeps results comparable.

**Trade-off:** The model cannot predict more than 125. A prediction at the cap means "at least about 125 cycles", and the assistant must phrase it that way. Caps of 115 or 130 would be equally defensible.

## D-009 — Tabular feature recipe
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebook 04, section 6

**Decision:** For row-wise models: 14 sensors, their 30-cycle rolling mean and standard deviation, and their change from the engine's own 20-cycle baseline (56 features). All features are causal.

**Why:** Validation RMSE within 100 cycles of failure fell from 21.7 (raw sensors) to 15.2. Change from baseline gave most of the gain (15.8 by itself); a 10-cycle rolling window gave none.

**Trade-off:** Baseline features require an engine's early cycles to be on record. The 20 and 30 values were not tuned exhaustively and were chosen with one probe model.

## D-010 — Standard scaling fitted on training engines only
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebook 03 section 2, notebook 04 section 7

**Decision:** Features for linear and neural models are standardised with a scaler fitted on the training engines of each split and applied unchanged to validation and test engines.

**Why:** Sensor noise is near-Gaussian without outliers. Fitting on all data would leak validation statistics into training.

## D-011 — Sequence windows of 30 cycles
**Date:** 2026-11-13 · **Phase:** 4 · **Evidence:** notebook 01, notebook 04 section 8

**Decision:** Sequence models receive windows of 30 consecutive cycles, labelled with the capped RUL at the last cycle. An engine is scored on its most recent window.

**Why:** The shortest test history is 31 cycles, so 30 is the longest window needing no padding.

**Trade-off:** Other lengths may perform better; that is a Phase 9 experiment.

## D-012 — Neural network inputs and comparison protocol
**Date:** 2026-11-13 · **Phase:** 6 · **Evidence:** notebook 06

**Decision:** Sequence models receive 28 channels per cycle: 14 scaled sensors plus their change from the engine's 20-cycle baseline. All architectures share one training recipe, the fixed 20-engine hold-out for early stopping, and three seeds each.

**Why:** Adding the baseline channels lowered hold-out RMSE by 1.3 to 2.8 cycles for every architecture, far more than the seed spread (0.2 to 0.3). Three seeds are needed because single runs differed by more than a cycle on the test set.

**Trade-off:** Hold-out scores for the networks are optimistic, since the same engines choose the stopping epoch. Only test results are used to compare networks with tree models.

## D-013 — XGBoost on tabular features is the working model
**Date:** 2026-11-13 · **Phase:** 6 · **Evidence:** notebooks 05 and 06

**Decision:** Explainability, uncertainty, the assistant and the application are built on XGBoost with the D-009 features.

**Why:** On the FD001 test set it is at least as accurate as the neural networks (like-for-like RMSE 14.6 against 15.8 to 16.4 for three-seed ensembles), trains in seconds, and has exact SHAP explanations. Random Forest scored slightly better (13.9) but is level with XGBoost in cross-validation, about seven times slower to train and much larger.

**Trade-off:** This holds for FD001. It must be re-examined on FD002 to FD004 in Phase 9.

## D-014 — Prediction ranges by conformalized quantile regression
**Date:** 2026-11-13 · **Phase:** 8 · **Evidence:** notebook 09

**Decision:** Each prediction carries a 90% range from two XGBoost quantile models (5% and 95%) with a conformal correction measured on 5-fold out-of-fold predictions by engine. In the application a range is stretched where needed to include its own point estimate, and a range whose upper end is at the cap is reported as "at least".

**Why:** Test coverage was 95% against a 90% target with an average width of 44 cycles. A fixed margin of similar average width covered only 73% in the 61 to 90 band and was uselessly wide near failure; the adaptive range was about 26 cycles wide near failure.

**Trade-off:** Coverage is an average over engines, not a per-engine promise. Three of the five misses were engines that failed sooner than their range, all with 21 or fewer cycles left. The stretching rule was adopted after seeing test results and is not part of the reported 95%.

## D-015 — The assistant speaks only from a fact sheet, with a rule-based fallback
**Date:** 2026-11-13 · **Phase:** 10 · **Evidence:** `src/assistant/`, `tests/test_pipeline.py`

**Decision:** The assistant receives one dictionary of facts per engine from the engine service and may state nothing else about the engine. A language model (Claude Opus 5.5 through the Anthropic SDK) writes the answer when a credential is configured; every number in its reply must appear in the fact sheet or the reply is discarded. A keyword-and-template answerer is always available and is used on any failure.

**Why:** An invented number about an engine could mislead a maintenance decision. Checking numbers is a simple test that catches the most damaging kind of invention. The fallback makes the system usable, testable and demonstrable without an API key or network.

**Trade-off:** The number check does not catch an invented statement that contains no number. The rule-based layer understands only a fixed set of question types. The language-model layer was not run against the live API during development (no credential on the machine).

## D-016 — Status bands and suggested actions are project conventions
**Date:** 2026-11-13 · **Phase:** 10 · **Evidence:** `src/assistant/knowledge.py`

**Decision:** Four status bands are defined from the estimate and the lower end of its range (estimate up to 30 or lower end up to 15; estimate up to 60; estimate below 100 or a closed range; otherwise no measurable wear). Each carries a suggestion worded as something to consider.

**Why:** A manager needs a headline, and the thresholds follow where notebooks 03 and 05 showed the model to be reliable. They are labelled in the output as a demonstration rule, not an aviation standard.

**Trade-off:** The thresholds are judgement, not derived from any maintenance programme, and would have to be replaced by an operator's own criteria.

## D-017 — FastAPI service with a Streamlit dashboard that talks to it over HTTP
**Date:** 2026-11-13 · **Phase:** 11 · **Evidence:** `api/main.py`, `dashboard/app.py`, `tests/test_api.py`

**Decision:** Modelling logic lives in `src/service`; FastAPI exposes it; Streamlit displays it and never imports a model.

**Why:** FastAPI gives input validation and generated documentation for little code. Streamlit builds an interactive dashboard in pure Python, which suits a single-developer research project. Keeping the dashboard behind the API means any other client gets the same answers.

**Trade-off:** Streamlit re-runs the script on each interaction and is not suited to many simultaneous users; a production front end would be a separate web application.

## D-018 — Lightweight monitoring and versioning; MLflow for experiments; no DVC or Evidently for now
**Date:** 2026-11-13 · **Phase:** 9 and 12 · **Evidence:** `src/monitoring/drift.py`, `scripts/train.py`, notebook 07

**Decision:** Experiments are tracked with MLflow (local SQLite store). Drift is measured with a Population Stability Index implemented in the project. Model versions are recorded in a JSON registry with data checksums. DVC, Evidently, Prometheus and Grafana are not adopted.

**Why:** The raw data never changes and is already protected by checksums, so DVC would add a tool without solving a problem here. The drift check needed is one statistic per sensor, which is thirty lines of tested code; a monitoring platform would add heavy dependencies to demonstrate the same idea. Prometheus and Grafana are for live services with real traffic.

**Trade-off:** These choices fit a demonstration. A deployed system with changing data and real traffic should use purpose-built tools, and this decision should be revisited then.

## D-019 — Docker removed
**Date:** 2026-11-25 · **Phase:** 12 · **Evidence:** owner's request

**Decision:** The Docker image, compose file and CI image build were removed. CI runs the Python tests and builds the web application instead.

**Why:** The owner asked for it. The container had never been built or run on this machine, so it was an untested claim rather than a working deliverable.

**Trade-off:** Running the project elsewhere now means following the README setup by hand (Python environment, Node.js, data download, training). A container could be added back later and should then be built and run before it is described as working.

## D-020 — NASA score constants: 13 for early, 10 for late
**Date:** 2026-11-25 · **Phase:** 5 · **Evidence:** `data/raw/Damage Propagation Modeling.pdf`, section on the scoring function and equation 11

**Decision:** Keep `nasa_score` as it is: an early estimate (d < 0) is penalised with exp(-d/13) - 1, a late one with exp(d/10) - 1.

**Why:** The paper gives a1 = 10 and a2 = 13 and states in words that "late predictions were more heavily penalized than early predictions". Of the two ways to assign the constants, only 10 on the late branch does that: a smaller divisor makes the penalty grow faster. This is also the form used throughout the RUL literature. The equation's layout could not be read reliably from the PDF's extracted text, so the decision rests on the paper's own stated intent.

**Trade-off:** None in practice; every reported NASA score stands.
