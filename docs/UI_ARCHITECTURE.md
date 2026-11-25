# UI Architecture Plan — Predictive Intelligence Web Application

Plan for the final user-facing application: a 3D engine "digital twin" interface with analytics and a conversational assistant, replacing the Streamlit dashboard as the main experience.

## 1. Principles

1. **Every number comes from the backend.** The frontend holds no engine data and computes no predictions. A value the API does not return is shown as "not available".
2. **The 3D engine is a picture, not a measurement.** It is a conceptual, procedurally built turbofan. Rotation speed and lighting are illustrative. What *is* real, and is drawn onto it, are the sensor readings and model outputs for the selected engine. The screen labels which is which.
3. **Nothing pretends to be live.** The data is the NASA C-MAPSS benchmark, replayed. The interface says "recorded history", never "live".
4. **The 3D scene is optional.** If WebGL is unavailable or fails, the rest of the application works and a static panel takes its place.
5. **Built in milestones.** A section that is not built yet is visibly marked as such in the navigation, not filled with sample values.

## 2. Technology choices

| Concern | Choice | Why | Not chosen |
|---|---|---|---|
| Framework | React 19 + TypeScript, built with Vite | The 3D ecosystem (React Three Fiber) is React-based; TypeScript catches mismatches with the API early | Extending Streamlit: it cannot host an interactive WebGL scene with this level of control |
| 3D | Three.js through React Three Fiber, helpers from Drei | Scene described as components, state shared with the rest of the UI | A downloaded GLB model: no licence-clear, technically suitable turbofan asset is in the project; a procedural model avoids licence risk and lets parts be highlighted individually |
| Charts | Plotly (`plotly.js-dist-min` + `react-plotly.js`) | Same library and visual theme as the notebooks; zoom, hover and click-to-select built in | A second charting library |
| Server state | TanStack Query | Caching, loading and error states for every API call without hand-written code | Fetching in `useEffect` |
| UI state | Zustand | A few shared values (selected engine, selected cycle, view mode) | Redux: too much ceremony for this size |
| Styling | Plain CSS with design tokens (CSS variables) | One small token file gives the whole visual identity; no build plug-ins | Tailwind: adds tooling without solving a problem here |
| Routing | React Router | Seven top-level sections | — |
| Backend | The existing FastAPI service, extended | Models, features and the fact sheet already live there | A second backend |

The Streamlit dashboard stays in the repository as a fallback interface.

## 3. System layout

```text
Browser (frontend/, Vite dev server on :5173, proxies /api to :8000)
  ├─ TopNav                       sections, dataset and engine indicator, analysis mode
  ├─ Engine Intelligence page     ← main screen
  │    ├─ EngineExplorer          left: dataset, engine list with real status, engine facts
  │    ├─ EngineScene             centre: 3D engine, view modes, camera and animation controls
  │    ├─ IntelligencePanel       right: estimate, range, status, contributing sensors, model
  │    └─ HistoryPanel            bottom: estimate + range over recorded flights, sensor trace, cycle selection
  ├─ Sensor Intelligence          21 sensors, compare, correlation
  ├─ AI Assistant                 chat, streaming, suggestions, plain-language mode, evidence
  ├─ Research Lab                 results from experiments/*.csv
  ├─ Model Center                 model registry, metrics, limitations
  ├─ Monitoring                   drift report, prediction log
  └─ Settings                     assistant provider status, display options

FastAPI (api/main.py)  →  src/service/engine_service.py  →  models + data
                       →  src/assistant/ (tool layer + language model + rule-based fallback)
```

## 4. Main screen: component breakdown

| Component | Shows | Data source |
|---|---|---|
| `TopNav` | Logo, sections, "FD001 · Engine 37 · flight 121 of 121", data-source badge | UI state + `/fleet` |
| `EngineExplorer` | Dataset tabs (FD001 selectable; FD002–004 marked "research results only"), searchable engine list with status dot and estimate, selected engine's recorded flights and sensor count | `/datasets`, `/fleet` |
| `EngineScene` | Procedural turbofan: nacelle, fan, LPC, HPC, combustor, HPT, LPT, nozzle. View modes: Overview, Components, Sensors, Health. Cutaway toggle, pause, reset camera, full screen | Geometry is local and conceptual. Sensor-station markers and their colours come from `/engines/{id}` and `/history` |
| `IntelligencePanel` | Estimated flights remaining, 90% range ("at least" when open-ended), status band, top contributing sensors with direction, model name and typical error, analysis time | `/engines/{id}?cycle=` |
| `HistoryPanel` | Estimate and range over recorded flights, benchmark true RUL at the last flight where the label exists, one selectable sensor trace, click a flight to inspect that point | `/engines/{id}/history` |

### What is real and what is illustrative in the 3D scene

| Element | Nature |
|---|---|
| Engine geometry and proportions | Conceptual. Not the geometry of any specific engine. Labelled on screen. |
| Fan and spool rotation | Illustrative animation at a fixed visual speed. Not driven by the recorded fan speed. |
| Sensor-station markers (stations 2, 15, 24, 30, 50) | Positions follow standard turbofan station numbering used in the NASA sensor names (T2, P15, T24, T30, T50). Approximate placement. |
| Marker readings | **Observed**: the recorded sensor value at the selected flight. |
| Marker and component colour in Health mode | **Model-derived**: SHAP contribution of the sensors measured at that station. |
| Estimate, range, status | **Model-derived**. |

No visual damage is drawn on the engine. The model estimates timing; it does not locate a defect, so showing one would be inventing it.

### Health indicator

There is **no 0–100 health score**. A single score would need a validated formula, and none exists in this project. The interface uses what was actually validated: the RUL estimate, its checked range, and the four status bands defined in `src/assistant/knowledge.py` (labelled as project conventions).

## 5. Backend additions

| Endpoint | Purpose | Milestone |
|---|---|---|
| `GET /datasets` | The four subsets, which one has a served model, real summary figures | 1 |
| `GET /fleet` | Every served engine with recorded flights, estimate, range and status | 1 |
| `GET /sensors` | All 21 sensors: symbol, description, unit, station, used by the model or constant | 1 |
| `GET /engines/{id}?cycle=N` | Fact sheet as of flight N (default: last recorded flight) | 1 |
| `GET /engines/{id}/history` | All 21 sensor traces, estimate and range per flight, benchmark label | 1 |
| `GET /engines/compare?a=&b=` | Two fact sheets side by side with differences | 3 |
| `POST /assistant/chat` (streamed) | Conversation with tool calls into the service | 3 |
| `GET /research/*` | Tables from `experiments/` | 4 |
| `GET /models`, `GET /monitoring` | Registry, drift report, prediction log summary | 4 |

## 6. Assistant architecture (Milestone 3)

```text
question + conversation + selected engine
        │
        ▼
language model  ──calls──►  tool layer (src/assistant/tools.py)
        ▲                     get_engine_summary · get_sensor_history · predict_remaining_useful_life
        │                     get_prediction_uncertainty · explain_prediction · compare_engines
        └──── tool results ◄─ get_model_information · explain_sensor
        │
        ▼
grounding check (numbers must appear in tool results)  →  streamed answer + evidence list
        │ on failure, no credential, or refusal
        ▼
rule-based answerer (always available)
```

- Each tool is a thin wrapper over `EngineService`; the model can read results but has no other source of engine facts.
- The engine is passed explicitly with every tool call, so one conversation cannot mix two engines' data.
- "Explain like I'm new to aviation" switches the instruction set and the rule-based templates, not the facts.
- The provider is configured by environment variable. No key is stored in the repository or the browser.
- Every answer lists which tools supplied its evidence and which layer wrote it.

## 7. Milestones

| # | Scope | Done when |
|---:|---|---|
| 1 | This plan; backend endpoints of section 5; app shell, navigation, visual tokens; Engine Explorer; 3D engine with rotation, orbit, zoom, reset, pause, cutaway, view modes, station markers; Intelligence panel; History panel with flight selection; WebGL fallback | Selecting any FD001 engine shows its real estimate, range, status, reasons and history; clicking a flight updates every panel; type-check and production build pass; API tests pass |
| 2 | Sensor Intelligence page (21 sensors, compare engines, correlation, link to importance); component inspection details; full-screen inspection; keyboard access | Every chart reads from the API |
| 3 | AI Assistant: tool layer, streamed chat, suggestions, history, copy, plain-language mode, evidence, engine comparison, Maintenance Intelligence summary | Works without a key (rule-based) and with one; grounding tests pass |
| 4 | Research Lab, Model Center, Monitoring, Settings | All figures generated from `experiments/` and the registry |
| 5 | Polish: loading skeletons, empty and error states, responsive panels, accessibility pass, production build served by FastAPI | Lighthouse accessibility check |

## 8. Known constraints

- **Only FD001 has a served model.** FD002–FD004 appear in the explorer as "research results only" and open the Research Lab, not an engine view. Serving them needs regime-normalised models wired into the service.
- **No ground truth during an engine's life.** The benchmark gives the true RUL only at each test engine's last recorded flight. "Actual versus predicted" is therefore one point per engine, not a curve.
- **Desktop first.** The three-panel main screen needs about 1280 px of width; narrower screens stack the panels.

## 9. Status (2026-11-13)

Milestones 1 to 4 are built: all seven sections read real data. Differences from the plan above:

- The assistant uses Google Gemini (the owner's choice of provider), not a streamed response: answers are verified against the tool results before they are shown.
- Engine comparison is a tool the assistant can call and a selector on the Sensor Intelligence page, not a separate endpoint.
- The Maintenance Intelligence summary is the briefing panel beside the chat.
- Milestone 5 (accessibility pass, code-splitting, serving the built front end from FastAPI, container update, front-end tests) is not done.
