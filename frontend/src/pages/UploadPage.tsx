import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { EngineFacts } from "../api";
import { COLOURS, CONFIG, Plot, layout } from "../chart";
import { IntelligencePanel, Skeleton } from "../components/panels";

interface UploadResult {
  needs_engine_choice: boolean;
  engines?: number[];
  message?: string;
  facts?: EngineFacts;
  history?: { sensors: Record<string, number[]>; estimates: { cycle: number[]; estimate: number[]; low: number[]; high: number[] } };
  file?: { name: string; flights: number; engines_in_file: number; engine_used: number };
}

/** A refusal carries the plain-language reasons the data was not accepted. */
class Refused extends Error {
  constructor(public reasons: string[]) { super("refused"); }
}

async function upload(filename: string, content: string, engineNumber: number | null): Promise<UploadResult> {
  const response = await fetch("/api/uploads", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, content, engine_number: engineNumber }),
  });
  if (response.ok) return response.json();
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  if (detail?.reasons) throw new Refused(detail.reasons);
  throw new Refused([typeof detail === "string" ? detail : "The file could not be processed. Check that it is a CSV or NASA text file."]);
}

export function UploadPage() {
  const [file, setFile] = useState<{ name: string; content: string } | null>(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const send = useMutation({
    mutationFn: ({ name, content, engine }: { name: string; content: string; engine: number | null }) => upload(name, content, engine),
  });

  const take = async (chosen: File | undefined) => {
    if (!chosen) return;
    const content = await chosen.text();
    setFile({ name: chosen.name, content });
    send.mutate({ name: chosen.name, content, engine: null });
  };
  const downloadReport = async (engine: number) => {
    if (!file) return;
    const response = await fetch("/api/uploads", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content: file.content, engine_number: engine, as_report: true }),
    });
    if (!response.ok) return;
    // Save the returned PDF as a file on the user's computer.
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = `engine_report_${file.name.replace(/\.[^.]+$/, "")}.pdf`;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const result = send.data;
  const refused = send.error instanceof Refused ? send.error.reasons : null;

  return (
    <main className="page">
      <header className="page-head">
        <h1>Upload Engine Data</h1>
        <p>Check one engine from a file of its recorded sensor readings. The file is read, checked and analysed; it is not saved.</p>
      </header>

      <div className="split">
        <section className="card">
          <h2>1. Choose a file</h2>
          <div className={"dropzone" + (dragging ? " over" : "")}
               onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
               onDrop={(e) => { e.preventDefault(); setDragging(false); void take(e.dataTransfer.files[0]); }}>
            <p>Drag a file here, or</p>
            <button onClick={() => input.current?.click()}>Choose a file</button>
            <input ref={input} type="file" accept=".csv,.txt" hidden onChange={(e) => { void take(e.target.files?.[0]); e.target.value = ""; }} />
            <p className="hint">CSV or NASA text file (.csv, .txt)</p>
          </div>
          {file && <p className="hint">Selected: <strong>{file.name}</strong></p>}
          <a className="link" href="/api/uploads/example" download="example_engine.csv">Download an example file</a>
        </section>

        <section className="card">
          <h2>What the file must contain</h2>
          <ul className="plain-list">
            <li><strong>One row per flight</strong>, starting at the engine's first flight, with none missing.</li>
            <li>A column named <code>cycle</code> (the flight number: 1, 2, 3 …).</li>
            <li>Columns <code>sensor_1</code> to <code>sensor_21</code>, in the same units as the NASA data.</li>
            <li>Optional: <code>setting_1</code> to <code>setting_3</code>.</li>
            <li>At least 31 flights for a dependable answer.</li>
          </ul>
          <p className="caution">This model only understands the engine type it was trained on: the NASA simulated turbofan at one flight condition. Data from a different engine, or in different units, is refused, because any answer would be meaningless.</p>
        </section>
      </div>

      {send.isPending && <section className="card"><h2>Checking the file…</h2><Skeleton lines={4} /></section>}

      {refused && (
        <section className="card refused" role="alert">
          <h2>This file was not accepted</h2>
          <p>No estimate has been made. Reason{refused.length > 1 ? "s" : ""}:</p>
          <ul className="plain-list">{refused.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          <p className="hint">Correct the file and upload it again. The example file shows the expected layout.</p>
        </section>
      )}

      {result?.needs_engine_choice && file && (
        <section className="card">
          <h2>2. Choose an engine</h2>
          <p>{result.message}</p>
          <label className="inline">Engine
            <select defaultValue="" onChange={(e) => e.target.value && send.mutate({ name: file.name, content: file.content, engine: Number(e.target.value) })}>
              <option value="" disabled>select…</option>
              {result.engines!.map((engine) => <option key={engine} value={engine}>Engine {engine}</option>)}
            </select>
          </label>
        </section>
      )}

      {result?.facts && result.history && result.file && (
        <>
          <div className={`banner ${result.facts.data_warnings.length ? "alert" : "ok"}`} role="status">
            <strong>{result.facts.data_warnings.length ? "Analysed, with warnings about the data" : "File accepted and analysed"}</strong>
            <span>{result.file.name}: {result.file.flights} flights{result.file.engines_in_file > 1 ? `, engine ${result.file.engine_used} of ${result.file.engines_in_file}` : ""}.</span>
          </div>
          {result.facts.data_warnings.length > 0 && (
            <section className="card refused">
              <h2>Check these before relying on the estimate</h2>
              <ul className="plain-list">{result.facts.data_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          )}
          <div className="upload-result">
            <section className="card">
              <h2>Estimate over the engine's recorded flights <span className="tag derived">model-derived</span></h2>
              <Plot
                data={[
                  { x: result.history.estimates.cycle, y: result.history.estimates.high, type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
                  { x: result.history.estimates.cycle, y: result.history.estimates.low, type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(217,119,87,0.22)", name: "90% range", hoverinfo: "skip" },
                  { x: result.history.estimates.cycle, y: result.history.estimates.estimate, type: "scatter", mode: "lines", line: { color: COLOURS.teal, width: 2.4 }, name: "Estimated flights remaining", hovertemplate: "flight %{x}<br>estimate %{y:.0f}<extra></extra>" },
                ]}
                layout={layout({ height: 320, xaxis: { gridcolor: "#2e2723", title: { text: "Flights completed" } }, yaxis: { gridcolor: "#2e2723", title: { text: "Flights remaining" }, range: [0, 140] } })}
                config={CONFIG} style={{ width: "100%" }} useResizeHandler />
              <p className="hint">Estimates start at flight 31. Unlike the demonstration engines, an uploaded engine has no known true answer to compare against.</p>
            </section>
            <IntelligencePanel facts={result.facts} loading={false} error={null} onDownload={() => void downloadReport(result.file!.engine_used)} />
          </div>
        </>
      )}
    </main>
  );
}
