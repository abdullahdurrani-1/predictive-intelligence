// Layout of the conceptual turbofan.
//
// This is a schematic, not the geometry of any real engine. Everything is laid
// out along one axis (y in model space; the scene rotates it to horizontal),
// with air entering at negative y and leaving at positive y.

import type { ComponentKey } from "../store";

export interface ComponentInfo {
  key: ComponentKey;
  name: string;
  what: string;
  /** Position along the engine axis, for labels and camera focus. */
  y: number;
  colour: string;
}

export const COMPONENTS: ComponentInfo[] = [
  { key: "fan", name: "Fan", y: -1.0, colour: "#d8cfc4",
    what: "The large front rotor. It moves most of the air around the core, which produces most of the thrust." },
  { key: "lpc", name: "Low-pressure compressor", y: 0.05, colour: "#c9a27e",
    what: "The first compressor stages, on the same shaft as the fan. They begin squeezing the air that enters the core." },
  { key: "hpc", name: "High-pressure compressor", y: 1.0, colour: "#d97757",
    what: "The main compressor. In this benchmark it is the component whose degradation is simulated in every subset." },
  { key: "combustor", name: "Combustor", y: 1.85, colour: "#e9b44c",
    what: "Where fuel is burned in the compressed air." },
  { key: "hpt", name: "High-pressure turbine", y: 2.33, colour: "#c8743f",
    what: "Extracts energy from the hot gas to drive the high-pressure compressor." },
  { key: "lpt", name: "Low-pressure turbine", y: 2.9, colour: "#a8896a",
    what: "Extracts further energy to drive the fan and low-pressure compressor." },
  { key: "nozzle", name: "Exhaust nozzle", y: 3.65, colour: "#a59a8f",
    what: "Where the core flow leaves the engine." },
];

export interface BladeRowSpec {
  component: ComponentKey;
  spool: "low" | "high";
  y: number;
  hubRadius: number;
  tipRadius: number;
  blades: number;
  chord: number;
}

function rows(component: ComponentKey, spool: "low" | "high", count: number, yStart: number, yEnd: number,
              hubStart: number, hubEnd: number, tipStart: number, tipEnd: number, blades: number, chord: number): BladeRowSpec[] {
  return Array.from({ length: count }, (_, i) => {
    const t = count === 1 ? 0 : i / (count - 1);
    return {
      component, spool, blades, chord,
      y: yStart + (yEnd - yStart) * t,
      hubRadius: hubStart + (hubEnd - hubStart) * t,
      tipRadius: tipStart + (tipEnd - tipStart) * t,
    };
  });
}

export const BLADE_ROWS: BladeRowSpec[] = [
  ...rows("fan", "low", 1, -1.0, -1.0, 0.42, 0.42, 1.38, 1.38, 22, 0.42),
  ...rows("lpc", "low", 3, -0.2, 0.3, 0.52, 0.56, 0.86, 0.82, 30, 0.1),
  ...rows("hpc", "high", 7, 0.55, 1.5, 0.5, 0.58, 0.8, 0.68, 34, 0.07),
  ...rows("hpt", "high", 2, 2.22, 2.44, 0.5, 0.5, 0.72, 0.76, 36, 0.09),
  ...rows("lpt", "low", 4, 2.66, 3.2, 0.42, 0.4, 0.78, 0.9, 38, 0.1),
];

/** Sensor stations, numbered as in the sensor symbols (T2, P15, T24, T30, T50). Placement is approximate. */
export const STATIONS: { id: string; y: number; radius: number }[] = [
  { id: "2", y: -1.45, radius: 1.0 },
  { id: "15", y: 0.7, radius: 1.25 },
  { id: "24", y: 0.42, radius: 0.92 },
  { id: "30", y: 1.58, radius: 0.78 },
  { id: "50", y: 3.3, radius: 0.98 },
];

// Lathe profiles as [radius, y] pairs.
export const NACELLE_PROFILE: [number, number][] = [
  [1.47, -1.62], [1.6, -1.55], [1.74, -1.1], [1.78, -0.3], [1.72, 0.6], [1.55, 1.42],
  [1.47, 1.42], [1.52, 0.6], [1.5, -0.3], [1.45, -1.1], [1.43, -1.5], [1.47, -1.62],
];
export const CORE_COWL_PROFILE: [number, number][] = [
  [0.9, -0.42], [0.98, 0.3], [0.96, 1.4], [0.92, 2.3], [0.98, 3.0], [0.9, 3.42],
  [0.86, 3.42], [0.94, 3.0], [0.88, 2.3], [0.92, 1.4], [0.94, 0.3], [0.88, -0.38], [0.9, -0.42],
];
export const NOZZLE_CONE_PROFILE: [number, number][] = [
  [0.4, 3.3], [0.36, 3.6], [0.22, 4.0], [0.02, 4.3],
];
