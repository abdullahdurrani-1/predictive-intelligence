# Architecture

How the pieces of Predictive Intelligence fit together, and why they are separated the way they are.

## The idea in one paragraph

Raw sensor readings go in. A single service turns them into a short **fact sheet** for one engine: an estimate of remaining flights, a range, a status, and the measurements that drove the estimate. Everything a person sees, whether a chart on the dashboard or a sentence from the assistant, is built from that fact sheet and nothing else. That one rule is what stops the system from saying things the model did not find.

## Data flow

```text
data/raw/*.txt                      NASA files, read-only, checksummed
      │
      ▼
src/data/cmapss.py                  load, name the columns
      │
      ▼
src/features/build.py               rolling mean / variability, change from engine's own baseline
(src/features/regimes.py)           per-flight-condition scaling for FD002 and FD004
      │
      ├──────────────► notebooks 05-10, scripts/train.py     training and experiments
      │                         │
      │                         ▼
      │                models/*.joblib + experiments/fd001_uncertainty.json
      ▼                         │
src/service/engine_service.py ◄─┘   point model + two quantile models + conformal correction + SHAP
      │
      │   fact sheet (plain dictionary)
      ▼
api/main.py  (FastAPI)              /engines, /engines/{id}, /history, /ask, /assess, /model, /health
      │                                         │
      ▼                                         ▼
dashboard/app.py  (Streamlit)        src/assistant/            answers in plain language
                                         assistant.py   language model + grounding check
                                         answers.py     rule-based answerer (always available)
                                         knowledge.py   status bands, limitations, glossary
```

## Components

| Component | Responsibility | Deliberately does not |
|---|---|---|
| `src/data` | Load files, split by whole engine | Clean or alter raw data |
| `src/features` | Causal features, RUL cap, windows, regime scaling | Use any future reading of an engine |
| `src/models` | Network definitions, training loop, prediction ranges | Decide which model is served |
| `src/explainability` | SHAP contributions, summed per sensor | Claim a cause |
| `src/service` | Build the fact sheet from a sensor history | Format text for people |
| `src/assistant` | Turn a fact sheet and a question into an answer | Read sensors or models directly |
| `api` | HTTP interface, input validation, request and prediction logging | Contain modelling logic |
| `dashboard` | Display; talks to the API over HTTP only | Import models |
| `src/monitoring`, `scripts/monitor_report.py` | Compare incoming data with training data; summarise predictions served | Retrain automatically |
| `scripts/train.py` | Retrain, evaluate, register, and promote only if not worse | Promote a model without a test score |

## The assistant's two layers

1. **Language model (optional).** With an Anthropic API credential configured, the question and the fact sheet are sent to Claude with instructions to use only the fact sheet. The reply is then checked: every number in it must appear in the fact sheet. A reply that fails is discarded.
2. **Rule-based answerer (always available).** Recognises common questions by keyword and writes the answer from templates filled with fact-sheet values. It cannot invent a number because it has no other source of numbers.

Layer 2 is used whenever layer 1 is unavailable, declines, or fails the check. Every answer reports which layer produced it. The language-model layer has not been exercised against the live API in this project's development environment, which had no credential; layer 2 is covered by tests.

Rules both layers follow: give the range with the estimate; say "at least" when the range reaches the model's limit; describe influencing measurements as what the model relied on, never as a diagnosed fault; never state or imply that an engine is safe to fly.

## Serving a prediction

1. Features are computed from the engine's full recorded history (the baseline feature needs the first 20 flights).
2. The point model gives the estimate; two quantile models give a band; the conformal correction from `experiments/fd001_uncertainty.json` is added to each end.
3. The band is clipped to 0–125 and stretched if needed to contain the estimate.
4. An upper end at 125 is reported as open-ended.
5. SHAP contributions for the latest row are summed per sensor and the top four returned with each sensor's early-life and recent levels.

## Operations

- **Model versions.** `scripts/train.py` writes every trained set to `models/registry/<UTC timestamp>/` and records parameters, metrics, data checksums and settings in `models/registry/registry.json`. The files in `models/` are the promoted (serving) version.
- **Monitoring.** The API appends one line per prediction to `monitoring/prediction_log.jsonl`. `scripts/monitor_report.py` computes a Population Stability Index for each sensor against the training data and exits with code 1 on a large change.
- **Retraining** is a manual decision triggered by a monitoring alert or new data, not an automatic loop: with safety-related predictions, a person should look before a model is replaced.
- **Experiments.** Notebook 07 logs runs to MLflow (`mlflow.db`); browse with `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
- **CI.** GitHub Actions runs the tests that need no data, and type-checks and builds the web application. Docker was removed at the owner's request (D-019).

## Known limits of the architecture

- The service holds the demonstration fleet in memory; there is no database.
- No authentication on the API. It is a local demonstration.
- Only the FD001 model is served. The multi-condition recipe exists in `src/data/prepare.py` and notebook 10 but is not wired into the service.
- Drift is checked on early-life readings only, and on sensors one at a time.
