import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, get } from "../api";
import { COLOURS, CONFIG, Plot, layout } from "../chart";
import { ErrorNote, Skeleton } from "../components/panels";
import { useApp } from "../store";

interface Analysis {
  sensors: string[];
  labels: string[];
  correlation: number[][];
  trend_with_rul: Record<string, number>;
  model_reliance_cycles: Record<string, number>;
  reliance_by_feature_kind_percent: Record<string, number>;
  basis: string;
  caution: string;
}

export function SensorsPage() {
  const { engineId } = useApp();
  const [selected, setSelected] = useState<string[]>(["sensor_11", "sensor_4"]);
  const [compareId, setCompareId] = useState<number | null>(null);

  const sensors = useQuery({ queryKey: ["sensors"], queryFn: api.sensors });
  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet });
  const analysis = useQuery({ queryKey: ["sensor-analysis"], queryFn: () => get<Analysis>("/sensors/analysis") });
  const history = useQuery({ queryKey: ["history", engineId], queryFn: () => api.history(engineId) });
  const other = useQuery({ queryKey: ["history", compareId], queryFn: () => api.history(compareId!), enabled: compareId !== null });

  if (sensors.error) return <main className="page"><ErrorNote error={sensors.error} /></main>;
  const toggle = (name: string) =>
    setSelected((current) => current.includes(name) ? current.filter((s) => s !== name) : [...current, name].slice(-4));
  const info = (name: string) => sensors.data?.sensors.find((s) => s.name === name);

  return (
    <main className="page">
      <header className="page-head">
        <h1>Sensor Intelligence</h1>
        <p>All 21 recorded measurements for Engine {engineId}. Readings are observed data; trend and reliance figures come from the training engines and the model.</p>
      </header>

      <div className="split">
        <section className="card">
          <h2>Sensors <span className="tag observed">select up to 4</span></h2>
          {!sensors.data ? <Skeleton lines={8} /> : (
            <div className="table-wrap tall">
              <table>
                <thead><tr><th></th><th>#</th><th>Measures</th><th>Where</th><th title="Rank correlation with remaining life across training engines">Trend with life</th><th title="Average effect on the estimate, in flights">Model reliance</th></tr></thead>
                <tbody>
                  {sensors.data.sensors.map((s) => (
                    <tr key={s.name} className={selected.includes(s.name) ? "picked" : ""}>
                      <td><input type="checkbox" checked={selected.includes(s.name)} onChange={() => toggle(s.name)} aria-label={`Show sensor ${s.number}`} /></td>
                      <td>{s.number}</td>
                      <td>{s.description} <em>({s.symbol}, {s.unit})</em></td>
                      <td>{s.station_name ?? "—"}</td>
                      <td>{s.used_by_model ? analysis.data?.trend_with_rul[s.name]?.toFixed(2) ?? "…" : "constant"}</td>
                      <td>{s.used_by_model ? analysis.data?.model_reliance_cycles[s.name]?.toFixed(1) ?? "…" : "not used"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="hint">{sensors.data?.naming_note} "Constant" sensors never change in FD001, so the model does not use them.</p>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>History on Engine {engineId} <span className="tag observed">observed</span></h2>
            <label className="inline">Compare with
              <select value={compareId ?? ""} onChange={(e) => setCompareId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">no other engine</option>
                {fleet.data?.engines.filter((e) => e.engine_id !== engineId).map((e) => (
                  <option key={e.engine_id} value={e.engine_id}>Engine {e.engine_id}</option>
                ))}
              </select>
            </label>
          </div>
          {!history.data ? <Skeleton lines={6} /> : selected.length === 0 ? <p className="hint">Select a sensor on the left.</p> : (
            selected.map((name) => (
              <Plot key={name}
                data={[
                  { x: history.data.sensors.cycle, y: history.data.sensors[name], type: "scatter", mode: "lines",
                    line: { color: COLOURS.amber, width: 1.3 }, name: `Engine ${engineId}` },
                  ...(other.data ? [{ x: other.data.sensors.cycle, y: other.data.sensors[name], type: "scatter" as const, mode: "lines" as const,
                    line: { color: COLOURS.blue, width: 1.3 }, name: `Engine ${compareId}` }] : []),
                ]}
                layout={layout({
                  height: 168, margin: { l: 62, r: 14, t: 26, b: 30 }, showlegend: Boolean(other.data),
                  title: { text: `${info(name)?.number}. ${info(name)?.description} (${info(name)?.symbol})`, font: { size: 12 }, x: 0.01, xanchor: "left" },
                  xaxis: { gridcolor: "#2e2723", linecolor: "#3a312c", tickfont: { color: "#a59a8f", size: 10 }, title: { text: "Flights completed", font: { size: 10 } } },
                  yaxis: { gridcolor: "#2e2723", linecolor: "#3a312c", tickfont: { color: "#a59a8f", size: 10 }, title: { text: info(name)?.unit ?? "", font: { size: 10 } } },
                })}
                config={CONFIG} style={{ width: "100%" }} useResizeHandler />
            ))
          )}
        </section>
      </div>

      <div className="split">
        <section className="card">
          <h2>How sensors move together <span className="tag derived">training engines</span></h2>
          {!analysis.data ? <Skeleton lines={6} /> : (
            <Plot
              data={[{ z: analysis.data.correlation, x: analysis.data.labels, y: analysis.data.labels, type: "heatmap", zmin: -1, zmax: 1,
                       colorscale: [[0, "#7b2d3b"], [0.5, "#231e1b"], [1, COLOURS.teal]], hovertemplate: "%{y} and %{x}<br>correlation %{z:.2f}<extra></extra>",
                       colorbar: { thickness: 10, len: 0.8, tickfont: { color: "#a59a8f" } } }]}
              layout={layout({ height: 430, margin: { l: 92, r: 10, t: 10, b: 92 }, xaxis: { tickangle: -50, tickfont: { size: 10, color: "#a59a8f" } },
                               yaxis: { autorange: "reversed", tickfont: { size: 10, color: "#a59a8f" } } })}
              config={CONFIG} style={{ width: "100%" }} useResizeHandler />
          )}
          <p className="hint">+1: two sensors rise and fall together. −1: one rises as the other falls. They correlate because they respond to the same wear.</p>
        </section>

        <section className="card">
          <h2>What the model relies on <span className="tag derived">model-derived</span></h2>
          {!analysis.data ? <Skeleton lines={6} /> : (() => {
            const order = [...analysis.data.sensors].sort((a, b) => analysis.data.model_reliance_cycles[a] - analysis.data.model_reliance_cycles[b]);
            const kinds = Object.entries(analysis.data.reliance_by_feature_kind_percent).sort((a, b) => b[1] - a[1]);
            return (
              <>
                <Plot
                  data={[{ type: "bar", orientation: "h", y: order.map((n) => analysis.data.labels[analysis.data.sensors.indexOf(n)]),
                           x: order.map((n) => analysis.data.model_reliance_cycles[n]), marker: { color: COLOURS.teal },
                           hovertemplate: "%{y}<br>moves the estimate by %{x:.1f} flights on average<extra></extra>" }]}
                  layout={layout({ height: 340, margin: { l: 92, r: 14, t: 6, b: 40 }, xaxis: { gridcolor: "#2e2723", tickfont: { color: "#a59a8f" }, title: { text: "Average effect on the estimate (flights)" } },
                                   yaxis: { tickfont: { size: 10.5, color: "#a59a8f" } } })}
                  config={CONFIG} style={{ width: "100%" }} useResizeHandler />
                <p className="hint">By kind of feature: {kinds.map(([kind, share]) => `${kind} ${share}%`).join(" · ")}.</p>
                <p className="hint">{analysis.data.basis}</p>
                <p className="caution">{analysis.data.caution}</p>
              </>
            );
          })()}
        </section>
      </div>
    </main>
  );
}
