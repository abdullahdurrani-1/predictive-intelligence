import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../api";
import { COLOURS, CONFIG, DataTable, Plot, layout, type Row } from "../chart";
import { ErrorNote, Skeleton } from "../components/panels";
import { useApp } from "../store";

const NOT_RUN = <p className="hint">Not available: the notebook that produces this table has not been run.</p>;
const num = (value: unknown) => (typeof value === "number" ? value : Number(value));

// ---------------------------------------------------------------- Research Lab

interface Research {
  ml_test: Row[] | null; ml_cv: Row[] | null; ml_predictions: Row[] | null;
  deep_test: Row[] | null; deep_validation: Row[] | null; deep_predictions: Row[] | null;
  deep_learning_curves: { model: string; train_rmse: number[]; validation_rmse: number[]; best_epoch: number }[];
  uncertainty_test: Row[] | null; all_subsets: Row[] | null; all_subsets_transfer: Row[] | null;
  all_subsets_uncertainty: Row[] | null; all_subsets_deep: Row[] | null;
  tuned_parameters: Record<string, number> | null; experiment_counts: Record<string, number>; source: string;
}

const RESEARCH_TABS = ["Model comparison", "Actual vs predicted", "Deep learning", "Uncertainty", "FD001–FD004", "Tuning"] as const;

export function ResearchPage() {
  const research = useQuery({ queryKey: ["research"], queryFn: () => get<Research>("/research") });
  const [tab, setTab] = useState<(typeof RESEARCH_TABS)[number]>("Model comparison");
  const [model, setModel] = useState("XGBoost");
  const data = research.data;

  const comparison = useMemo(() => {
    if (!data?.ml_test) return [];
    const rows = data.ml_test.filter((r) => r.model !== "Predict the average").map((r) => ({ name: String(r.model), rmse: num(r.RMSE), family: "Traditional (100 engines)" }));
    for (const r of data.deep_test ?? []) {
      if (r["ensemble RMSE"] !== null) rows.push({ name: `${r.model} (3-seed ensemble)`, rmse: num(r["ensemble RMSE"]), family: "Neural network (80 engines)" });
    }
    return rows.sort((a, b) => b.rmse - a.rmse);
  }, [data]);

  const predictionSets = useMemo(() => {
    const sets: Record<string, { truth: number[]; predicted: number[] }> = {};
    for (const table of [data?.ml_predictions, data?.deep_predictions]) {
      if (!table) continue;
      for (const column of Object.keys(table[0]).filter((c) => !["engine_id", "true_rul"].includes(c))) {
        sets[column] = { truth: table.map((r) => num(r.true_rul)), predicted: table.map((r) => num(r[column])) };
      }
    }
    return sets;
  }, [data]);
  const chosen = predictionSets[model] ?? Object.values(predictionSets)[0];

  return (
    <main className="page">
      <header className="page-head">
        <h1>Research Lab</h1>
        <p>Results of the experiments in notebooks 05 to 10, read from the files those notebooks wrote. {data?.source}</p>
      </header>
      <div className="segmented wide" role="tablist">
        {RESEARCH_TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}
      </div>
      {research.error ? <ErrorNote error={research.error} /> : !data ? <Skeleton lines={8} /> : (
        <>
          {tab === "Model comparison" && (
            <div className="split">
              <section className="card">
                <h2>FD001 test set: error by model</h2>
                {comparison.length === 0 ? NOT_RUN : (
                  <Plot data={[{ type: "bar", orientation: "h", y: comparison.map((r) => r.name), x: comparison.map((r) => r.rmse),
                                 marker: { color: comparison.map((r) => r.family.startsWith("Neural") ? COLOURS.teal : COLOURS.silver) },
                                 text: comparison.map((r) => r.rmse.toFixed(1)), textposition: "outside", hovertemplate: "%{y}<br>RMSE %{x:.2f} flights<extra></extra>" }]}
                        layout={layout({ height: 360, margin: { l: 190, r: 40, t: 8, b: 44 }, xaxis: { gridcolor: "#2e2723", tickfont: { color: "#a59a8f" }, title: { text: "Test RMSE in flights (lower is better)" } } })}
                        config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                )}
                <p className="hint">Light: traditional models trained on all 100 engines. Orange: neural networks trained on 80 (20 held out for early stopping). Truth as recorded, predictions limited to 0–125.</p>
              </section>
              <section className="card">
                <h2>Traditional models: test results</h2>
                {data.ml_test ? <DataTable rows={data.ml_test} columns={["model", "RMSE", "MAE", "NASA score", "late by more than 20"]} /> : NOT_RUN}
                <h2 style={{ marginTop: 18 }}>Cross-validation (training engines only)</h2>
                {data.ml_cv ? <DataTable rows={data.ml_cv} columns={["model", "RMSE (all rows)", "± RMSE", "MAE (all rows)", "seconds"]} /> : NOT_RUN}
              </section>
            </div>
          )}

          {tab === "Actual vs predicted" && (
            <section className="card">
              <div className="card-head">
                <h2>True against predicted remaining life, 100 FD001 test engines</h2>
                <label className="inline">Model
                  <select value={model} onChange={(e) => setModel(e.target.value)}>
                    {Object.keys(predictionSets).map((name) => <option key={name}>{name}</option>)}
                  </select>
                </label>
              </div>
              {!chosen ? NOT_RUN : (
                <div className="split">
                  <Plot data={[
                          { x: [0, 150], y: [0, 150], type: "scatter", mode: "lines", line: { color: COLOURS.muted, dash: "dash", width: 1 }, name: "perfect", hoverinfo: "skip" },
                          { x: chosen.truth, y: chosen.predicted, type: "scatter", mode: "markers", name: "test engines",
                            marker: { size: 7, color: chosen.predicted.map((p, i) => (p > chosen.truth[i] ? COLOURS.amber : COLOURS.good)) },
                            hovertemplate: "true %{x}<br>predicted %{y:.0f}<extra></extra>" },
                        ]}
                        layout={layout({ height: 420, xaxis: { gridcolor: "#2e2723", title: { text: "True remaining life (flights)" }, range: [0, 150] },
                                         yaxis: { gridcolor: "#2e2723", title: { text: "Predicted (flights)" }, range: [0, 150] },
                                         shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 125, y1: 125, line: { color: "#6e625a", dash: "dot", width: 1 } }] })}
                        config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                  <Plot data={[{ x: chosen.predicted.map((p, i) => p - chosen.truth[i]), type: "histogram", marker: { color: COLOURS.blue }, nbinsx: 26 } as never]}
                        layout={layout({ height: 420, xaxis: { gridcolor: "#2e2723", title: { text: "Error: predicted − true (flights). Positive = late" } }, yaxis: { gridcolor: "#2e2723", title: { text: "Engines" } } })}
                        config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                </div>
              )}
              <p className="hint">Gold points are late predictions (the engine failed sooner than predicted). The dotted line is the model's 125-flight limit: engines with more life than that are necessarily underestimated.</p>
            </section>
          )}

          {tab === "Deep learning" && (
            <div className="split">
              <section className="card">
                <h2>Learning curves (seed 0)</h2>
                {data.deep_learning_curves.length === 0 ? NOT_RUN : (
                  <Plot data={data.deep_learning_curves.flatMap((run, i) => {
                          const colour = [COLOURS.teal, COLOURS.blue, COLOURS.amber, COLOURS.silver][i % 4];
                          const epochs = run.validation_rmse.map((_, e) => e + 1);
                          return [
                            { x: epochs, y: run.validation_rmse, type: "scatter" as const, mode: "lines" as const, line: { color: colour, width: 2 }, name: `${run.model} hold-out` },
                            { x: epochs, y: run.train_rmse, type: "scatter" as const, mode: "lines" as const, line: { color: colour, width: 1, dash: "dot" as const }, name: `${run.model} training`, showlegend: false },
                          ];
                        })}
                        layout={layout({ height: 360, xaxis: { gridcolor: "#2e2723", title: { text: "Epoch" } }, yaxis: { gridcolor: "#2e2723", title: { text: "RMSE (flights)" }, range: [8, 22] } })}
                        config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                )}
                <p className="hint">Solid: hold-out engines. Dotted: training engines. Training error keeps falling while hold-out error flattens, which is why training is stopped early.</p>
              </section>
              <section className="card">
                <h2>Hold-out engines (three seeds each)</h2>
                {data.deep_validation ? <DataTable rows={data.deep_validation} columns={["model", "validation RMSE (mean of 3 seeds)", "spread across seeds (sd)", "weights", "training seconds (mean)"]}
                                                    labels={{ "validation RMSE (mean of 3 seeds)": "Hold-out RMSE", "spread across seeds (sd)": "Seed spread", "training seconds (mean)": "Seconds" }} /> : NOT_RUN}
                <h2 style={{ marginTop: 18 }}>Test set</h2>
                {data.deep_test ? <DataTable rows={data.deep_test} columns={["model", "RMSE (mean of seeds)", "RMSE sd", "ensemble RMSE", "ensemble NASA score"]}
                                              labels={{ "RMSE (mean of seeds)": "RMSE", "RMSE sd": "Seed spread" }} /> : NOT_RUN}
                <p className="hint">The networks looked better than XGBoost on the hold-out engines and worse on the test set. Runs saved: {Object.entries(data.experiment_counts).map(([k, v]) => `${v} ${k}`).join("; ")}.</p>
              </section>
            </div>
          )}

          {tab === "Uncertainty" && (
            <div className="split">
              <section className="card">
                <h2>90% ranges on the FD001 test set</h2>
                {data.uncertainty_test ? <DataTable rows={data.uncertainty_test} columns={["method", "coverage, capped truth (%)", "average width (cycles)", "truth below range (failed sooner)", "truth above range (lasted longer)"]}
                                                     labels={{ "coverage, capped truth (%)": "Inside range (%)", "average width (cycles)": "Width (flights)", "truth below range (failed sooner)": "Failed sooner", "truth above range (lasted longer)": "Lasted longer" }} /> : NOT_RUN}
                <p className="hint">Target: 90% of engines inside the range. With 100 engines, a correct method typically lands between about 84% and 96%.</p>
              </section>
              <section className="card">
                <h2>The same method on all four subsets</h2>
                {data.all_subsets_uncertainty ? <DataTable rows={data.all_subsets_uncertainty} columns={["subset", "test coverage (%)", "average width (cycles)", "failed sooner than range", "coverage, true RUL up to 30 (%)"]}
                                                            labels={{ "test coverage (%)": "Inside range (%)", "average width (cycles)": "Width", "failed sooner than range": "Failed sooner", "coverage, true RUL up to 30 (%)": "Inside, near failure (%)" }} /> : NOT_RUN}
                <p className="caution">Near failure the range holds less often on the multi-condition subsets (FD002, FD004). The lower end of a range is not a safety margin.</p>
              </section>
            </div>
          )}

          {tab === "FD001–FD004" && (
            <div className="split">
              <section className="card">
                <h2>One recipe on all four subsets (XGBoost, untuned)</h2>
                {data.all_subsets ? <DataTable rows={data.all_subsets} columns={["subset", "CV RMSE", "test RMSE", "test RMSE (truth capped)", "test engines", "engines above the cap"]}
                                                labels={{ "test RMSE (truth capped)": "Test RMSE, truth capped", "engines above the cap": "Above 125-flight cap" }} /> : NOT_RUN}
                <p className="hint">The uncapped test error is much larger on FD002 and FD004 because about a quarter of their test engines have more than 125 flights left, which a capped model cannot express.</p>
                <h2 style={{ marginTop: 18 }}>Neural networks on each subset</h2>
                {data.all_subsets_deep ? <DataTable rows={data.all_subsets_deep} columns={["subset", "model", "runs", "test RMSE", "RMSE sd over seeds"]} labels={{ "RMSE sd over seeds": "Seed spread" }} /> : NOT_RUN}
              </section>
              <section className="card">
                <h2>Moving a model between subsets</h2>
                {!data.all_subsets_transfer ? NOT_RUN : (() => {
                  const subsets = ["FD001", "FD002", "FD003", "FD004"];
                  const z = data.all_subsets_transfer.map((row) => subsets.map((s) => num(row[s])));
                  return (
                    <Plot data={[{ z, x: subsets, y: data.all_subsets_transfer.map((r) => String(r["trained on"])), type: "heatmap", colorscale: "Cividis", reversescale: true,
                                   text: z.map((r) => r.map((v) => v.toFixed(1))) as never, texttemplate: "%{text}", hovertemplate: "trained on %{y}, tested on %{x}<br>RMSE %{z:.1f}<extra></extra>",
                                   colorbar: { thickness: 10, tickfont: { color: "#a59a8f" } } } as never]}
                          layout={layout({ height: 380, margin: { l: 70, r: 10, t: 10, b: 50 }, xaxis: { title: { text: "Tested on" } }, yaxis: { title: { text: "Trained on" }, autorange: "reversed" } })}
                          config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                  );
                })()}
                <p className="hint">Test RMSE in flights. A model that has never seen a fault mode (FD001 → FD003) loses far more than one moved from six flight conditions to one (FD002 → FD001).</p>
              </section>
            </div>
          )}

          {tab === "Tuning" && (
            <section className="card">
              <h2>Hyperparameter search (Optuna, 25 trials, FD001)</h2>
              {data.tuned_parameters ? (
                <DataTable rows={Object.entries(data.tuned_parameters).map(([setting, value]) => ({ setting, "best value found": value }))} columns={["setting", "best value found"]} />
              ) : NOT_RUN}
              <p className="hint">Result recorded in notebook 07: the search improved test RMSE from 14.78 to 14.42 (five seeds each), about a third of a flight, after roughly 19 minutes. The served model keeps the default settings. Individual trials are in the MLflow log (<code>mlflow ui --backend-store-uri sqlite:///mlflow.db</code>).</p>
            </section>
          )}
        </>
      )}
    </main>
  );
}

// ---------------------------------------------------------------- Model Center

interface Models {
  served_model: {
    name: string; training_data: string; target: string; validation: string; file_last_written: string; registry_version: string;
    typical_error_flights: number | null;
    architecture: Record<string, string | number>;
    range: { method: string; target_percent: number; measured_percent: number; average_width_flights: number };
  };
  registry: { version: string; promoted: boolean; metrics: Record<string, number>; params: Record<string, number> }[];
  limitations: string[]; notice: string;
}

export function ModelsPage() {
  const models = useQuery({ queryKey: ["models"], queryFn: () => get<Models>("/models") });
  const research = useQuery({ queryKey: ["research"], queryFn: () => get<Research>("/research") });
  if (models.error) return <main className="page"><ErrorNote error={models.error} /></main>;
  const m = models.data?.served_model;
  return (
    <main className="page">
      <header className="page-head"><h1>Model Center</h1><p>The model behind every estimate in this application, how it was checked, and where it should not be trusted.</p></header>
      {!m ? <Skeleton lines={8} /> : (
        <>
          <div className="split three">
            <section className="card">
              <h2>Served model</h2>
              <dl className="facts">
                <dt>Name</dt><dd>{m.name}</dd>
                <dt>Type</dt><dd>{m.architecture.type}</dd>
                <dt>Size</dt><dd>{m.architecture.trees} trees, depth {m.architecture.max_depth}, learning rate {m.architecture.learning_rate}</dd>
                <dt>Inputs</dt><dd>{m.architecture.inputs}</dd>
                <dt>Range models</dt><dd>{m.architecture.companions}</dd>
              </dl>
            </section>
            <section className="card">
              <h2>Training and validation</h2>
              <dl className="facts">
                <dt>Training data</dt><dd>{m.training_data}</dd>
                <dt>Target</dt><dd>{m.target}</dd>
                <dt>Validation</dt><dd>{m.validation}</dd>
                <dt>Model file written</dt><dd>{new Date(m.file_last_written).toLocaleString()}</dd>
                <dt>Version</dt><dd>{m.registry_version}</dd>
              </dl>
            </section>
            <section className="card">
              <h2>Measured performance</h2>
              <dl className="facts">
                <dt>Typical error</dt><dd>{m.typical_error_flights === null ? "not available" : `about ${m.typical_error_flights} flights (test set)`}</dd>
                <dt>Range method</dt><dd>{m.range.method}</dd>
                <dt>Range target</dt><dd>{m.range.target_percent}% of engines inside</dd>
                <dt>Range measured</dt><dd>{m.range.measured_percent}% of 100 test engines inside</dd>
                <dt>Average range width</dt><dd>{m.range.average_width_flights} flights</dd>
              </dl>
            </section>
          </div>
          <div className="split">
            <section className="card">
              <h2>Performance comparison (FD001 test set)</h2>
              {research.data?.ml_test ? <DataTable rows={research.data.ml_test} columns={["model", "RMSE", "MAE", "NASA score"]} /> : NOT_RUN}
              <h2 style={{ marginTop: 18 }}>Registered training runs</h2>
              {models.data!.registry.length === 0 ? <p className="hint">No runs registered yet. Run <code>python scripts/train.py</code> to create one.</p> : (
                <DataTable rows={models.data!.registry.map((v) => ({ version: v.version, served: v.promoted ? "yes" : "no", "CV RMSE": v.metrics.cv_rmse, "test RMSE": v.metrics.test_rmse, "range inside (%)": v.metrics.test_range_coverage_percent }))}
                           columns={["version", "served", "CV RMSE", "test RMSE", "range inside (%)"]} />
              )}
            </section>
            <section className="card">
              <h2>Limitations</h2>
              <ul className="plain-list">{models.data!.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              <p className="caution">{models.data!.notice}</p>
            </section>
          </div>
        </>
      )}
    </main>
  );
}

// ---------------------------------------------------------------- Monitoring

interface Monitoring {
  drift: Row[]; largest_psi: number; alert: boolean; drift_injected: boolean;
  thresholds: { no_meaningful_change_below: number; large_change_above: number };
  reference: string; incoming: string; explanation: string;
  predictions: { predictions_served: number; mean_estimate: number; share_near_end_of_life_percent: number; share_open_ended_range_percent: number; status_counts: Record<string, number> } | null;
  recent_predictions: Row[];
}

export function MonitoringPage() {
  const [inject, setInject] = useState(false);
  const monitoring = useQuery({ queryKey: ["monitoring", inject], queryFn: () => get<Monitoring>(`/monitoring?inject_drift=${inject}`), staleTime: 0 });
  const data = monitoring.data;
  return (
    <main className="page">
      <header className="page-head"><h1>Monitoring</h1><p>Whether incoming readings still resemble the data the model learned from, and what the system has been predicting.</p></header>
      {monitoring.error ? <ErrorNote error={monitoring.error} /> : !data ? <Skeleton lines={8} /> : (
        <>
          <div className={`banner ${data.alert ? "alert" : "ok"}`} role="status">
            <strong>{data.alert ? "Large change detected in incoming data" : "No large change in incoming data"}</strong>
            <span>Largest stability index: {data.largest_psi.toFixed(3)} (alert above {data.thresholds.large_change_above}).
              {data.drift_injected && " A sensor fault is being simulated for this demonstration; it is not real data."}</span>
            <label className="switch"><input type="checkbox" checked={inject} onChange={(e) => setInject(e.target.checked)} /> Simulate a fault on sensor 11</label>
          </div>
          <div className="split">
            <section className="card">
              <h2>Data drift by sensor</h2>
              <Plot data={[{ type: "bar", orientation: "h", y: [...data.drift].reverse().map((r) => `${String(r.feature).replace("sensor_", "S")} ${r.symbol}`), x: [...data.drift].reverse().map((r) => num(r.psi)),
                             marker: { color: [...data.drift].reverse().map((r) => num(r.psi) >= data.thresholds.large_change_above ? COLOURS.red : num(r.psi) >= data.thresholds.no_meaningful_change_below ? COLOURS.amber : COLOURS.good) },
                             hovertemplate: "%{y}<br>stability index %{x:.3f}<extra></extra>" }]}
                    layout={layout({ height: 380, margin: { l: 92, r: 16, t: 8, b: 44 }, xaxis: { gridcolor: "#2e2723", title: { text: "Population Stability Index" } },
                                     shapes: [data.thresholds.no_meaningful_change_below, data.thresholds.large_change_above].map((x) => ({ type: "line" as const, x0: x, x1: x, yref: "paper" as const, y0: 0, y1: 1, line: { color: "#6e625a", dash: "dash" as const, width: 1 } })) })}
                    config={CONFIG} style={{ width: "100%" }} useResizeHandler />
              <p className="hint">{data.explanation}</p>
              <p className="hint">Reference: {data.reference}. Incoming: {data.incoming}.</p>
            </section>
            <section className="card">
              <h2>Predictions served</h2>
              {!data.predictions ? <p className="hint">No predictions have been logged yet. Open an engine or run <code>python scripts/simulate_stream.py</code>.</p> : (
                <>
                  <dl className="facts">
                    <dt>Predictions logged</dt><dd>{data.predictions.predictions_served}</dd>
                    <dt>Average estimate</dt><dd>{data.predictions.mean_estimate} flights</dd>
                    <dt>Rated near end of predicted life</dt><dd>{data.predictions.share_near_end_of_life_percent}%</dd>
                    <dt>Reported as "at least"</dt><dd>{data.predictions.share_open_ended_range_percent}%</dd>
                  </dl>
                  <h2 style={{ marginTop: 18 }}>Most recent</h2>
                  <DataTable rows={data.recent_predictions.map((r) => ({ ...r, time: new Date(String(r.time)).toLocaleTimeString(), high: r.high ?? "open" }))}
                             columns={["time", "engine", "cycles_recorded", "estimate", "low", "high", "status"]}
                             labels={{ cycles_recorded: "flights", status: "status" }} />
                </>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}

// ---------------------------------------------------------------- Settings

interface Settings {
  assistant: { provider: string; model: string; key_configured: boolean; fallback: string };
  data: { source: string; served_subset: string; engines: number; raw_file_checksums_recorded: boolean };
  model_settings: Record<string, number>; notice: string;
}

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => get<Settings>("/settings") });
  const { plainLanguage, setPlainLanguage, paused, togglePaused } = useApp();
  if (settings.error) return <main className="page"><ErrorNote error={settings.error} /></main>;
  const s = settings.data;
  return (
    <main className="page">
      <header className="page-head"><h1>Settings</h1><p>How this installation is configured. Keys and model settings are set on the server, not in the browser.</p></header>
      {!s ? <Skeleton lines={6} /> : (
        <div className="split three">
          <section className="card">
            <h2>Assistant</h2>
            <dl className="facts">
              <dt>Provider</dt><dd>{s.assistant.provider}</dd>
              <dt>Model</dt><dd>{s.assistant.model}</dd>
              <dt>API key</dt><dd style={{ color: s.assistant.key_configured ? COLOURS.good : COLOURS.amber }}>{s.assistant.key_configured ? "configured on the server" : "not configured"}</dd>
              <dt>Fallback</dt><dd>{s.assistant.fallback}</dd>
            </dl>
            <p className="hint">The key is read from the <code>GOOGLE_API_KEY</code> environment variable or the project's <code>.env</code> file. It is never sent to the browser. Set <code>GEMINI_MODEL</code> to use a different model.</p>
          </section>
          <section className="card">
            <h2>Display</h2>
            <label className="switch"><input type="checkbox" checked={plainLanguage} onChange={(e) => setPlainLanguage(e.target.checked)} /> Assistant explains like I'm new to aviation</label>
            <label className="switch"><input type="checkbox" checked={paused} onChange={togglePaused} /> Pause the 3D engine animation</label>
            <p className="hint">These preferences apply to this browser session.</p>
          </section>
          <section className="card">
            <h2>Data and model settings</h2>
            <dl className="facts">
              <dt>Data source</dt><dd>{s.data.source}</dd>
              <dt>Served subset</dt><dd>{s.data.served_subset}, {s.data.engines} engines</dd>
              <dt>Raw-file checksums</dt><dd>{s.data.raw_file_checksums_recorded ? "recorded" : "not recorded"}</dd>
              {Object.entries(s.model_settings).map(([k, v]) => <Fragment key={k}><dt>{k.replace(/_/g, " ")}</dt><dd>{v}</dd></Fragment>)}
            </dl>
            <p className="caution">{s.notice}</p>
          </section>
        </div>
      )}
    </main>
  );
}
