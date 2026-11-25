import { Component, Suspense, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Html, Instance, Instances, Lightformer, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { EngineFacts, EngineHistory, Sensor } from "../api";
import { useApp, type ComponentKey } from "../store";
import {
  BLADE_ROWS, COMPONENTS, CORE_COWL_PROFILE, NACELLE_PROFILE, NOZZLE_CONE_PROFILE, STATIONS, type BladeRowSpec,
} from "./engineModel";

const TEAL = "#8fbf9a";
const AMBER = "#e9b44c";
const NEUTRAL = "#9c9187";

function lathe(profile: [number, number][], cutaway: boolean) {
  const points = profile.map(([radius, y]) => new THREE.Vector2(radius, y));
  // Leaving out a wedge of the revolution gives the cutaway without any clipping tricks.
  // The removed wedge faces up and towards the default camera.
  return new THREE.LatheGeometry(points, 96, cutaway ? Math.PI * 0.08 : 0, cutaway ? Math.PI * 1.3 : Math.PI * 2);
}

function useComponentLook(key: ComponentKey) {
  const viewMode = useApp((s) => s.viewMode);
  const selected = useApp((s) => s.component);
  const info = COMPONENTS.find((c) => c.key === key)!;
  if (viewMode !== "components") return { colour: "#a39a90", emissive: "#000000", opacity: 1 };
  if (selected === null) return { colour: info.colour, emissive: "#000000", opacity: 1 };
  return selected === key
    ? { colour: info.colour, emissive: info.colour, opacity: 1 }
    : { colour: "#5a504a", emissive: "#000000", opacity: 0.35 };
}

function BladeRow({ spec }: { spec: BladeRowSpec }) {
  const look = useComponentLook(spec.component);
  const select = useApp((s) => s.selectComponent);
  const viewMode = useApp((s) => s.viewMode);
  const span = spec.tipRadius - spec.hubRadius;
  const angles = useMemo(() => Array.from({ length: spec.blades }, (_, i) => (i / spec.blades) * Math.PI * 2), [spec.blades]);
  const pick = viewMode === "components"
    ? (event: { stopPropagation: () => void }) => { event.stopPropagation(); select(spec.component); }
    : undefined;

  return (
    <group position={[0, spec.y, 0]} onClick={pick}>
      <mesh>
        <cylinderGeometry args={[spec.hubRadius, spec.hubRadius, spec.chord * 1.15, 40]} />
        <meshStandardMaterial color={look.colour} metalness={0.85} roughness={0.35} transparent opacity={look.opacity} />
      </mesh>
      <Instances limit={spec.blades}>
        <boxGeometry args={[span, spec.chord, spec.component === "fan" ? 0.03 : 0.018]} />
        <meshStandardMaterial color={look.colour} emissive={look.emissive} emissiveIntensity={0.35}
                              metalness={0.9} roughness={0.28} transparent opacity={look.opacity} />
        {angles.map((angle) => (
          // Each blade sits on the hub, points outwards, and is twisted so it meets the airflow at an angle.
          <group key={angle} rotation={[0, angle, 0]}>
            <Instance position={[spec.hubRadius + span / 2, 0, 0]} rotation={[0.85, 0, 0]} />
          </group>
        ))}
      </Instances>
    </group>
  );
}

function Spool({ which, speed }: { which: "low" | "high"; speed: number }) {
  const group = useRef<THREE.Group>(null);
  const paused = useApp((s) => s.paused);
  // Illustrative rotation at a fixed visual speed. It is not driven by the recorded shaft speed.
  useFrame((_, delta) => { if (!paused && group.current) group.current.rotation.y += delta * speed; });
  return (
    <group ref={group}>
      {BLADE_ROWS.filter((row) => row.spool === which).map((row) => <BladeRow key={`${row.component}-${row.y}`} spec={row} />)}
      {which === "low" && (
        <>
          <mesh position={[0, -1.32, 0]} rotation={[Math.PI, 0, 0]}>
            <coneGeometry args={[0.42, 0.62, 40]} />
            <meshStandardMaterial color="#e6ddd2" metalness={0.9} roughness={0.25} />
          </mesh>
          <mesh position={[0, 1.1, 0]}>
            <cylinderGeometry args={[0.12, 0.12, 4.4, 20]} />
            <meshStandardMaterial color="#6b6058" metalness={0.9} roughness={0.4} />
          </mesh>
        </>
      )}
    </group>
  );
}

function Casings() {
  const cutaway = useApp((s) => s.cutaway);
  const viewMode = useApp((s) => s.viewMode);
  const select = useApp((s) => s.selectComponent);
  const combustor = useComponentLook("combustor");
  const nozzle = useComponentLook("nozzle");
  const nacelle = useMemo(() => lathe(NACELLE_PROFILE, cutaway), [cutaway]);
  const cowl = useMemo(() => lathe(CORE_COWL_PROFILE, cutaway), [cutaway]);
  const cone = useMemo(() => lathe(NOZZLE_CONE_PROFILE, false), []);
  const pick = (key: ComponentKey) => viewMode === "components"
    ? (event: { stopPropagation: () => void }) => { event.stopPropagation(); select(key); }
    : undefined;
  const shell = viewMode === "overview" ? 1 : 0.5;

  return (
    <>
      <mesh geometry={nacelle}>
        <meshStandardMaterial color="#efe8df" metalness={0.35} roughness={0.42} side={THREE.DoubleSide} transparent opacity={shell} />
      </mesh>
      <mesh geometry={cowl}>
        <meshStandardMaterial color="#7a6e65" metalness={0.75} roughness={0.4} side={THREE.DoubleSide} transparent opacity={shell} />
      </mesh>
      <mesh position={[0, 1.85, 0]} rotation={[Math.PI / 2, 0, 0]} onClick={pick("combustor")}>
        <torusGeometry args={[0.62, 0.16, 20, 60]} />
        <meshStandardMaterial color={combustor.colour} emissive={viewMode === "components" ? combustor.emissive : AMBER}
                              emissiveIntensity={0.3} metalness={0.6} roughness={0.5} transparent opacity={combustor.opacity} />
      </mesh>
      <mesh geometry={cone} onClick={pick("nozzle")}>
        <meshStandardMaterial color={nozzle.colour} emissive={nozzle.emissive} emissiveIntensity={0.3}
                              metalness={0.8} roughness={0.35} side={THREE.DoubleSide} transparent opacity={nozzle.opacity} />
      </mesh>
    </>
  );
}

interface StationData { id: string; name: string; readings: { symbol: string; value: number; unit: string }[]; influence: number | null }

function StationMarkers({ stations }: { stations: StationData[] }) {
  const viewMode = useApp((s) => s.viewMode);
  // Only one station's readings are open at a time, so labels never pile up on each other.
  const [open, setOpen] = useState<string | null>("30");
  if (viewMode !== "sensors" && viewMode !== "health") return null;
  return (
    <>
      {STATIONS.map((place) => {
        const data = stations.find((s) => s.id === place.id);
        if (!data) return null;
        const colour = viewMode === "health" && data.influence !== null ? (data.influence < 0 ? AMBER : TEAL) : NEUTRAL;
        const isOpen = open === place.id;
        return (
          <group key={place.id} position={[0, place.y, place.radius]}>
            <mesh>
              <sphereGeometry args={[0.055, 20, 20]} />
              <meshStandardMaterial color={colour} emissive={colour} emissiveIntensity={0.9} />
            </mesh>
            <Html position={[0, 0, 0.1]} zIndexRange={isOpen ? [40, 30] : [20, 10]}>
              <div className={"station" + (isOpen ? " open" : "")} style={{ borderColor: colour }}>
                <button onClick={() => setOpen(isOpen ? null : place.id)} aria-expanded={isOpen}
                        title={`Station ${data.id}: ${data.name}`}>
                  <b style={{ background: colour }}>{data.id}</b>{data.name}
                </button>
                {isOpen && (
                  <div className="station-readings">
                    {data.readings.map((reading) => (
                      <span key={reading.symbol}>{reading.symbol} <i>{reading.value.toFixed(2)} {reading.unit}</i></span>
                    ))}
                    {viewMode === "health" && (
                      <em>{data.influence === null
                        ? "Not among the model's 4 main influences"
                        : `Model: ${data.influence > 0 ? "+" : ""}${data.influence.toFixed(1)} flights`}</em>
                    )}
                  </div>
                )}
              </div>
            </Html>
          </group>
        );
      })}
    </>
  );
}

/** If WebGL fails after start-up, show the fallback instead of breaking the page. */
class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

// The point the camera orbits: the middle of the engine.
const ENGINE_TARGET: [number, number, number] = [0.1, 0, 0];

const CAMERA_VIEWS: Record<string, [number, number, number]> = {
  "Three-quarter": [-5.6, 3.0, 7.6],
  Front: [-11.5, 0.6, 0.01],
  Side: [0.3, 0.4, 11.5],
  Rear: [10.5, 2.0, 4.0],
};

export function EngineScene({ facts, history, sensors }: { facts?: EngineFacts; history?: EngineHistory; sensors?: Sensor[] }) {
  const { viewMode, setViewMode, paused, togglePaused, cutaway, toggleCutaway, component, selectComponent } = useApp();
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null);
  const frame = useRef<HTMLDivElement>(null);
  const [supported] = useState(webglAvailable);

  // Observed readings at the inspected flight, grouped by the station where they are measured.
  const stations = useMemo<StationData[]>(() => {
    if (!facts || !history || !sensors) return [];
    const index = Math.min(facts.cycles_recorded, history.sensors.cycle.length) - 1;
    const byStation = new Map<string, StationData>();
    for (const sensor of sensors) {
      if (!sensor.station || !sensor.station_name) continue;
      const entry = byStation.get(sensor.station)
        ?? { id: sensor.station, name: sensor.station_name, readings: [], influence: null };
      entry.readings.push({ symbol: sensor.symbol, value: history.sensors[sensor.name][index], unit: sensor.unit });
      const reason = facts.main_reasons.find((r) => r.sensor === sensor.name);
      if (reason) entry.influence = (entry.influence ?? 0) + reason.cycles;
      byStation.set(sensor.station, entry);
    }
    return [...byStation.values()];
  }, [facts, history, sensors]);

  const moveCamera = (position: [number, number, number]) => {
    const orbit = controls.current;
    if (!orbit) return;
    orbit.object.position.set(...position);
    orbit.target.set(...ENGINE_TARGET);
    orbit.update();
  };
  const fullScreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void frame.current?.requestFullscreen();
  };

  const fallback = (
    <div className="scene-fallback" role="img" aria-label="3D view unavailable">
      <strong>3D view unavailable</strong>
      <p>This browser or device could not start WebGL. The analysis panels and history below are unaffected.</p>
    </div>
  );
  const selectedInfo = COMPONENTS.find((c) => c.key === component);
  const modes: { key: typeof viewMode; label: string }[] = [
    { key: "overview", label: "3D view" }, { key: "components", label: "Components" },
    { key: "sensors", label: "Sensors" }, { key: "health", label: "Model influence" },
  ];

  return (
    <div className="scene" ref={frame}>
      <div className="scene-toolbar" role="toolbar" aria-label="Engine view">
        <div className="segmented">
          {modes.map((mode) => (
            <button key={mode.key} className={viewMode === mode.key ? "active" : ""} aria-pressed={viewMode === mode.key}
                    onClick={() => setViewMode(mode.key)}>{mode.label}</button>
          ))}
        </div>
        <div className="scene-actions">
          {Object.entries(CAMERA_VIEWS).map(([name, position]) => (
            <button key={name} onClick={() => moveCamera(position)} title={`Camera: ${name}`}>{name}</button>
          ))}
          <button onClick={toggleCutaway} aria-pressed={cutaway}>{cutaway ? "Close casing" : "Cutaway"}</button>
          <button onClick={togglePaused} aria-pressed={paused}>{paused ? "Resume" : "Pause"}</button>
          <button onClick={() => moveCamera(CAMERA_VIEWS["Three-quarter"])}>Reset</button>
          <button onClick={fullScreen}>Full screen</button>
        </div>
      </div>

      {supported ? (
        <SceneBoundary fallback={fallback}>
          <Canvas camera={{ position: CAMERA_VIEWS["Three-quarter"], fov: 32 }} dpr={[1, 2]} onPointerMissed={() => selectComponent(null)}>
            <color attach="background" args={["#131110"]} />
            <hemisphereLight args={["#ffe8d6", "#17110f", 0.45]} />
            <directionalLight position={[-6, 7, 6]} intensity={1.8} />
            <directionalLight position={[7, -2, -5]} intensity={0.6} color="#f0b99b" />
            {/* Metal needs something to reflect. These soft light panels are generated locally; nothing is downloaded. */}
            <Environment resolution={256}>
              <Lightformer form="rect" intensity={3.2} position={[0, 6, 2]} scale={[14, 5, 1]} rotation={[Math.PI / 2, 0, 0]} />
              <Lightformer form="rect" intensity={1.6} position={[-8, 1, 4]} scale={[6, 8, 1]} rotation={[0, Math.PI / 2, 0]} color="#ffe8d6" />
              <Lightformer form="rect" intensity={1.0} position={[8, -1, -4]} scale={[6, 8, 1]} rotation={[0, -Math.PI / 2, 0]} color="#f0b99b" />
              <Lightformer form="rect" intensity={0.5} position={[0, -6, 0]} scale={[14, 6, 1]} rotation={[-Math.PI / 2, 0, 0]} color="#2a201c" />
            </Environment>
            <pointLight position={[1.8, 0, 0]} intensity={viewMode === "health" ? 5 : 2} color={AMBER} distance={3} />
            <Suspense fallback={null}>
              {/* The model is built along y; this rotation lays it horizontal with the inlet on the left. */}
              <group rotation={[0, 0, -Math.PI / 2]} position={[-1.2, 0, 0]}>
                <Casings />
                <Spool which="low" speed={2.2} />
                <Spool which="high" speed={5.5} />
                <StationMarkers stations={stations} />
              </group>
            </Suspense>
            <OrbitControls ref={controls} target={ENGINE_TARGET} enablePan={false} minDistance={4} maxDistance={18}
                           enableDamping dampingFactor={0.08} />
          </Canvas>
        </SceneBoundary>
      ) : fallback}

      {viewMode === "components" && (
        <div className="scene-note">
          {selectedInfo
            ? <><strong>{selectedInfo.name}</strong><span>{selectedInfo.what}</span></>
            : <span>Select a part of the engine to see what it does.</span>}
        </div>
      )}
      {viewMode === "sensors" && (
        <div className="scene-note">
          <strong>Observed readings at flight {facts?.cycles_recorded ?? "—"}</strong>
          <span>Shown at the stations named in the sensor symbols. Shaft speeds, ratios and bleeds have no single location and are listed in the panels, not on the engine.</span>
        </div>
      )}
      {viewMode === "health" && (
        <div className="scene-note">
          <strong>Model-derived</strong>
          <span>Gold: readings here lowered the estimate. Green: raised it. This shows what the model relied on, not where a fault is.</span>
        </div>
      )}
      <div className="scene-disclaimer">
        Conceptual engine model · rotation is an illustrative animation, not a live feed · data: NASA C-MAPSS simulation
      </div>
    </div>
  );
}
