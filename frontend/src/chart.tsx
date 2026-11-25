import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import type { Layout } from "plotly.js";

export const Plot = createPlotlyComponent(Plotly);

export const COLOURS = { good: "#8fbf9a", teal: "#d97757", blue: "#c9a27e", amber: "#e9b44c", red: "#d1495b", silver: "#d8cfc4", muted: "#a59a8f" };
export const AXIS = { gridcolor: "#2e2723", zerolinecolor: "#2e2723", linecolor: "#3a312c", tickfont: { color: "#a59a8f", size: 11 }, automargin: true };

/** Shared chart look, so every figure in the application matches the notebooks' theme. */
export function layout(overrides: Partial<Layout> = {}): Partial<Layout> {
  return {
    autosize: true, height: 300, margin: { l: 56, r: 20, t: 14, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: "#ddd5cb", size: 11.5 },
    xaxis: { ...AXIS }, yaxis: { ...AXIS }, legend: { orientation: "h", y: 1.14, x: 0, font: { size: 11 } },
    hoverlabel: { bgcolor: "#231e1b", font: { color: "#f5f0ea" } },
    ...overrides,
  };
}

export const CONFIG = { displayModeBar: false, responsive: true };

export type Row = Record<string, number | string | null>;

/** A plain table for rows returned by the API. Missing values are shown as "not available". */
export function DataTable({ rows, columns, labels = {} }: { rows: Row[]; columns: string[]; labels?: Record<string, string> }) {
  const show = (value: number | string | null | undefined) =>
    value === null || value === undefined || value === "" ? "—"
      : typeof value === "number" ? (Number.isInteger(value) ? String(value) : value.toFixed(2)) : value;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((c) => <th key={c}>{labels[c] ?? c}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, i) => <tr key={i}>{columns.map((c) => <td key={c}>{show(row[c])}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}
