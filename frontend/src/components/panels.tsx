import { useMemo, useState } from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { STATUS_COLOUR, rangeText, type Dataset, type EngineFacts, type EngineHistory, type FleetEngine, type Sensor } from "../api";
import { useApp } from "../store";

const Plot = createPlotlyComponent(Plotly);

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <div key={i} style={{ width: `${90 - i * 14}%` }} />)}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return <div className="error-note" role="alert">Could not load this section. {error instanceof Error ? error.message : ""}</div>;
}

// ---------------------------------------------------------------- left: explorer

export function EngineExplorer({ datasets, engines }: { datasets?: Dataset[]; engines?: FleetEngine[] }) {
  const { engineId, selectEngine } = useApp();
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState<"id" | "estimate">("id");
  const [dataset, setDataset] = useState("FD001");
  const chosen = datasets?.find((d) => d.name === dataset);

  const visible = useMemo(() => {
    const filtered = (engines ?? []).filter((e) => String(e.engine_id).includes(search.trim()));
    return order === "id" ? filtered : [...filtered].sort((a, b) => a.estimate_cycles - b.estimate_cycles);
  }, [engines, search, order]);
  const current = engines?.find((e) => e.engine_id === engineId);

  return (
    <aside className="panel explorer" aria-label="Engine explorer">
      <h2>Engine explorer</h2>
      <div className="dataset-tabs" role="tablist" aria-label="Dataset">
        {(datasets ?? []).map((d) => (
          <button key={d.name} role="tab" aria-selected={dataset === d.name} className={dataset === d.name ? "active" : ""}
                  onClick={() => setDataset(d.name)} title={d.description}>{d.name}</button>
        ))}
      </div>
      {chosen && <p className="hint">{chosen.description}. {chosen.availability}.</p>}

      {chosen && !chosen.served ? (
        <div className="unserved">
          <p>No model is served for {chosen.name} in this build, so its engines cannot be opened here.</p>
          <dl>
            <dt>Test engines</dt><dd>{chosen.test_engines ?? "not available"}</dd>
            <dt>Cross-validated RMSE</dt><dd>{chosen.cv_rmse ?? "not available"}</dd>
            <dt>Test RMSE (truth capped)</dt><dd>{chosen.test_rmse_truth_capped ?? "not available"}</dd>
          </dl>
          <p className="hint">Figures from the research notebooks (notebook 10).</p>
        </div>
      ) : (
        <>
          {current && (
            <dl className="engine-facts">
              <dt>Engine</dt><dd>{current.engine_id}</dd>
              <dt>Flights recorded</dt><dd>{current.cycles_recorded}</dd>
              <dt>Sensors recorded</dt><dd>21 (14 used by the model)</dd>
            </dl>
          )}
          <div className="list-controls">
            <input type="search" placeholder="Find engine number" value={search} aria-label="Find engine number"
                   onChange={(event) => setSearch(event.target.value)} />
            <button onClick={() => setOrder(order === "id" ? "estimate" : "id")} title="Change sort order">
              {order === "id" ? "By number" : "Lowest estimate first"}
            </button>
          </div>
          {!engines ? <Skeleton lines={6} /> : (
            <ul className="engine-list">
              {visible.map((engine) => (
                <li key={engine.engine_id}>
                  <button className={engine.engine_id === engineId ? "active" : ""} onClick={() => selectEngine(engine.engine_id)}
                          aria-current={engine.engine_id === engineId}>
                    <span className="dot" style={{ background: STATUS_COLOUR[engine.status_key] }} title={engine.status_label} />
                    <span className="name">Engine {engine.engine_id}</span>
                    <span className="value">{engine.range_is_open_ended ? `${engine.range_low_cycles}+` : engine.estimate_cycles}</span>
                  </button>
                </li>
              ))}
              {visible.length === 0 && <li className="hint">No engine matches.</li>}
            </ul>
          )}
          <p className="hint">Number: estimated flights remaining at the last recorded flight. "93+" means at least 93.</p>
        </>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------- right: intelligence

export function IntelligencePanel({ facts, loading, error, onDownload }: { facts?: EngineFacts; loading: boolean; error: unknown; onDownload?: () => void }) {
  if (error) return <aside className="panel intelligence"><h2>Engine intelligence</h2><ErrorNote error={error} /></aside>;
  if (loading || !facts) return <aside className="panel intelligence"><h2>Engine intelligence</h2><Skeleton lines={8} /></aside>;
  const colour = STATUS_COLOUR[facts.status.key];
  const largest = Math.max(...facts.main_reasons.map((r) => Math.abs(r.cycles)), 1);

  return (
    <aside className="panel intelligence" aria-label="Engine intelligence">
      <h2>Engine intelligence <span className="tag derived">model-derived</span></h2>
      <p className="context">
        {facts.engine} · as of flight {facts.cycles_recorded} of {facts.last_recorded_cycle}
        {!facts.is_latest_cycle && " (earlier point in its history)"}
      </p>

      <div className="status" style={{ borderColor: colour }}>
        <strong style={{ color: colour }}>{facts.status.label}</strong>
        <span>{facts.status.plain}</span>
      </div>

      {facts.data_warnings.length > 0 && (
        <div className="data-warning" role="alert">
          <strong>Check the data</strong>
          {facts.data_warnings.map((warning) => <span key={warning}>{warning}</span>)}
        </div>
      )}

      <div className="headline">
        <div>
          <span className="label">Estimated flights remaining</span>
          <span className="figure">{facts.estimate_cycles}</span>
        </div>
        <div>
          <span className="label">{facts.range_confidence_percent}% range</span>
          <span className="figure small">{rangeText(facts)}</span>
        </div>
      </div>
      <p className="hint">
        {facts.range_is_open_ended
          ? `The model cannot see beyond ${facts.rul_cap_cycles} flights, so it reports a minimum.`
          : "About one engine in ten falls outside a range like this. It is not a safe operating window."}
        {facts.limited_history && " Fewer flights are on record than the model was tested with; treat with extra caution."}
      </p>

      {onDownload && (
        <button className="download" onClick={onDownload} title="A PDF report you can save, print or send">Download report (PDF)</button>
      )}

      <h3>What moved the estimate</h3>
      <ul className="reasons">
        {facts.main_reasons.map((reason) => (
          <li key={reason.sensor}>
            <div className="reason-head">
              <span>{reason.description} <em>({reason.symbol})</em></span>
              <span style={{ color: reason.cycles < 0 ? "var(--amber)" : "var(--good)" }}>
                {reason.cycles > 0 ? "+" : ""}{reason.cycles.toFixed(1)}
              </span>
            </div>
            <div className="bar"><div style={{ width: `${(Math.abs(reason.cycles) / largest) * 100}%`,
                                                background: reason.cycles < 0 ? "var(--amber)" : "var(--good)" }} /></div>
            <span className="hint">
              now {reason.recent_level} {reason.unit}, {reason.movement} early life ({reason.early_life_level})
            </span>
          </li>
        ))}
      </ul>
      <p className="hint">Effect in flights, relative to the model's average estimate of {facts.model_average_estimate_cycles}.
        These are the readings the model relied on, not a diagnosed cause.</p>

      <h3>Something to consider</h3>
      <p>{facts.status.consider}</p>
      <p className="hint">Status and suggestion: {facts.status.basis}.</p>

      <h3>Model</h3>
      <dl className="model">
        <dt>Model</dt><dd>{facts.model.name}</dd>
        <dt>Typical error</dt><dd>{facts.model.typical_error_cycles === null ? "not available" : `about ${facts.model.typical_error_cycles} flights`}</dd>
        <dt>Range checked on test engines</dt><dd>{facts.model.measured_range_coverage_percent}% inside</dd>
        <dt>Analysed</dt><dd>{new Date(facts.analysed_at).toLocaleString()}</dd>
      </dl>
    </aside>
  );
}

// ---------------------------------------------------------------- bottom: history

const AXIS = { gridcolor: "#2e2723", zerolinecolor: "#2e2723", linecolor: "#3a312c", tickfont: { color: "#a59a8f", size: 11 } };

export function HistoryPanel({ history, facts, sensors }: { history?: EngineHistory; facts?: EngineFacts; sensors?: Sensor[] }) {
  const selectCycle = useApp((s) => s.selectCycle);
  const selectedCycle = useApp((s) => s.cycle);
  const [sensorName, setSensorName] = useState("sensor_11");
  const sensor = sensors?.find((s) => s.name === sensorName);

  if (!history || !facts) return <section className="panel history"><h2>Engine history</h2><Skeleton lines={4} /></section>;
  const { estimates, benchmark_label: label } = history;
  const inspected = facts.cycles_recorded;
  const lastCycle = history.sensors.cycle[history.sensors.cycle.length - 1];

  return (
    <section className="panel history" aria-label="Engine history">
      <div className="history-head">
        <h2>Engine history <span className="tag observed">recorded flights</span></h2>
        <div className="history-controls">
          <label>Sensor
            <select value={sensorName} onChange={(event) => setSensorName(event.target.value)}>
              {(sensors ?? []).map((s) => (
                <option key={s.name} value={s.name}>{s.number}. {s.description} ({s.symbol}){s.used_by_model ? "" : " — constant"}</option>
              ))}
            </select>
          </label>
          <span className="hint">Inspecting flight {inspected}</span>
          <button onClick={() => selectCycle(null)} disabled={facts.is_latest_cycle}>Back to latest flight</button>
        </div>
      </div>
      <div className="flight-slider">
        <label htmlFor="flight">Flight</label>
        <input id="flight" type="range" min={1} max={lastCycle} value={selectedCycle ?? lastCycle}
               aria-valuetext={`Flight ${selectedCycle ?? lastCycle} of ${lastCycle}`}
               onChange={(event) => { const flight = Number(event.target.value); selectCycle(flight >= lastCycle ? null : flight); }} />
        <span>{selectedCycle ?? lastCycle} of {lastCycle}</span>
      </div>
      <Plot
        data={[
          { x: estimates.cycle, y: estimates.high, type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
          { x: estimates.cycle, y: estimates.low, type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty",
            fillcolor: "rgba(217,119,87,0.22)", name: "90% range (model)", hoverinfo: "skip" },
          { x: estimates.cycle, y: estimates.estimate, type: "scatter", mode: "lines", line: { color: "#d97757", width: 2.4 },
            name: "Estimated flights remaining (model)", hovertemplate: "flight %{x}<br>estimate %{y:.0f}<extra></extra>" },
          { x: [label.cycle], y: [label.true_rul], type: "scatter", mode: "markers",
            marker: { color: "#f5f0ea", size: 10, symbol: "diamond", line: { color: "#131110", width: 1 } },
            name: "True value at last flight (benchmark label)", hovertemplate: "true remaining life %{y}<extra></extra>" },
          { x: history.sensors.cycle, y: history.sensors[sensorName], type: "scatter", mode: "lines", yaxis: "y2",
            line: { color: "#e9b44c", width: 1.2 }, name: `${sensor?.symbol ?? sensorName} (observed)`,
            hovertemplate: `flight %{x}<br>%{y} ${sensor?.unit ?? ""}<extra></extra>` },
        ]}
        layout={{
          autosize: true, height: 212, margin: { l: 52, r: 56, t: 6, b: 34 },
          paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: "#ddd5cb", size: 11 },
          xaxis: { ...AXIS, title: { text: "Flights completed" }, range: [1, lastCycle] },
          yaxis: { ...AXIS, title: { text: "Flights remaining" }, range: [0, 140] },
          yaxis2: { ...AXIS, overlaying: "y", side: "right", showgrid: false, title: { text: sensor?.unit ?? "" } },
          legend: { orientation: "h", y: 1.16, x: 0, font: { size: 10.5 } },
          hovermode: "x", dragmode: false,
          shapes: [
            { type: "line", x0: inspected, x1: inspected, yref: "paper", y0: 0, y1: 1, line: { color: "#f5f0ea", width: 1, dash: "dot" } },
            { type: "line", xref: "paper", x0: 0, x1: 1, y0: facts.rul_cap_cycles, y1: facts.rul_cap_cycles, line: { color: "#6e625a", width: 1, dash: "dash" } },
          ],
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
        useResizeHandler
        onClick={(event) => {
          const flight = Number(event.points[0]?.x);
          if (Number.isFinite(flight) && flight >= 1) selectCycle(flight >= lastCycle ? null : Math.round(flight));
        }}
      />
      <p className="hint">Drag the slider (or use the arrow keys) to see what the model would have said at that point, using only the readings up to then.
        Estimates start at flight 31. The dashed line is the model's {facts.rul_cap_cycles}-flight limit. {label.note}</p>
    </section>
  );
}
