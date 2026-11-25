// Typed access to the FastAPI service. The frontend holds no engine data of
// its own: every value on screen is fetched through one of these functions.

export type StatusKey = "no_measurable_wear" | "early_wear" | "advanced_wear" | "near_end_of_predicted_life";

export interface Dataset {
  name: string;
  description: string;
  served: boolean;
  availability: string;
  test_engines: number | null;
  cv_rmse: number | null;
  test_rmse_truth_capped: number | null;
}

export interface FleetEngine {
  engine_id: number;
  cycles_recorded: number;
  estimate_cycles: number;
  range_low_cycles: number;
  range_high_cycles: number | null;
  range_is_open_ended: boolean;
  status_key: StatusKey;
  status_label: string;
}

export interface Sensor {
  name: string;
  number: number;
  symbol: string;
  description: string;
  unit: string;
  station: string | null;
  station_name: string | null;
  used_by_model: boolean;
  note: string | null;
}

export interface Reason {
  sensor: string;
  symbol: string;
  description: string;
  cycles: number;
  effect: string;
  unit: string;
  early_life_level: number;
  recent_level: number;
  change_percent: number;
  movement: string;
}

export interface EngineFacts {
  engine: string;
  engine_id: number;
  data_source: string;
  cycles_recorded: number;
  last_recorded_cycle: number;
  is_latest_cycle: boolean;
  limited_history: boolean;
  data_warnings: string[];
  estimate_cycles: number;
  range_low_cycles: number;
  range_high_cycles: number | null;
  range_is_open_ended: boolean;
  range_confidence_percent: number;
  rul_cap_cycles: number;
  status: { key: StatusKey; label: string; plain: string; consider: string; basis: string };
  model_average_estimate_cycles: number;
  main_reasons: Reason[];
  model: {
    name: string;
    typical_error_cycles: number | null;
    range_method: string;
    measured_range_coverage_percent: number;
  };
  limitations: string[];
  analysed_at: string;
}

export interface EngineHistory {
  engine_id: number;
  sensors: Record<string, number[]>;
  estimates: { cycle: number[]; estimate: number[]; low: number[]; high: number[] };
  benchmark_label: { cycle: number; true_rul: number; note: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const detail = await response.json().then((body) => body.detail).catch(() => response.statusText);
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const get = <T,>(path: string) => request<T>(path);
export const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  datasets: () => get<{ datasets: Dataset[]; source: string }>("/datasets"),
  fleet: () => get<{ dataset: string; engines: FleetEngine[] }>("/fleet"),
  sensors: () => get<{ sensors: Sensor[]; naming_note: string }>("/sensors"),
  engine: (id: number, cycle: number | null) =>
    get<EngineFacts>(`/engines/${id}${cycle === null ? "" : `?cycle=${cycle}`}`),
  history: (id: number) => get<EngineHistory>(`/engines/${id}/history`),
  settings: () => get<{ assistant: { provider: string; model: string; key_configured: boolean; fallback: string } }>("/settings"),
};

export const STATUS_COLOUR: Record<StatusKey, string> = {
  no_measurable_wear: "var(--good)",
  early_wear: "var(--blue)",
  advanced_wear: "var(--amber)",
  near_end_of_predicted_life: "var(--red)",
};

/** "21 to 50" or "at least 93": the range exactly as the backend reports it. */
export function rangeText(item: { range_low_cycles: number; range_high_cycles: number | null; range_is_open_ended: boolean }) {
  return item.range_is_open_ended || item.range_high_cycles === null
    ? `at least ${item.range_low_cycles}`
    : `${item.range_low_cycles} to ${item.range_high_cycles}`;
}
