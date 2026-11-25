import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, rangeText } from "./api";
import { EngineExplorer, ErrorNote, HistoryPanel, IntelligencePanel } from "./components/panels";
import { EngineScene } from "./scene/EngineScene";
import { AssistantPage } from "./pages/AssistantPage";
import { ModelsPage, MonitoringPage, ResearchPage, SettingsPage } from "./pages/InfoPages";
import { SensorsPage } from "./pages/SensorsPage";
import { UploadPage } from "./pages/UploadPage";
import { useApp } from "./store";

const sections = () => [
  { path: "/engine", label: "Engine Intelligence", element: <EngineIntelligencePage /> },
  { path: "/sensors", label: "Sensor Intelligence", element: <SensorsPage /> },
  { path: "/assistant", label: "AI Assistant", element: <AssistantPage /> },
  { path: "/upload", label: "Upload Engine Data", element: <UploadPage /> },
  { path: "/research", label: "Research Lab", element: <ResearchPage /> },
  { path: "/models", label: "Model Center", element: <ModelsPage /> },
  { path: "/monitoring", label: "Monitoring", element: <MonitoringPage /> },
  { path: "/settings", label: "Settings", element: <SettingsPage /> },
];

function TopNav() {
  const { engineId, cycle } = useApp();
  return (
    <header className="topnav">
      <div className="brand" aria-label="Predictive Intelligence">
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="1.4" />
          {[0, 60, 120, 180, 240, 300].map((angle) => (
            <path key={angle} d="M12 12 L12 3.2 Q14.6 7.5 12 12" fill="currentColor" transform={`rotate(${angle} 12 12)`} />
          ))}
        </svg>
        <span>Predictive Intelligence</span>
      </div>
      <nav aria-label="Sections">
        {sections().map((section) => (
          <NavLink key={section.path} to={section.path} className={({ isActive }) => (isActive ? "active" : "")}>
            {section.label}
          </NavLink>
        ))}
      </nav>
      <div className="context-chip" title="Current selection">
        <span>FD001</span><span>Engine {engineId}</span><span>{cycle === null ? "latest flight" : `flight ${cycle}`}</span>
      </div>
      <div className="source-badge" title="All engine data in this application comes from the NASA C-MAPSS simulation">Simulated benchmark data</div>
    </header>
  );
}

function EngineIntelligencePage() {
  const { engineId, cycle } = useApp();
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet });
  const sensors = useQuery({ queryKey: ["sensors"], queryFn: api.sensors });
  const history = useQuery({ queryKey: ["history", engineId], queryFn: () => api.history(engineId) });
  const facts = useQuery({
    queryKey: ["engine", engineId, cycle], queryFn: () => api.engine(engineId, cycle),
    placeholderData: (previous) => (previous?.engine_id === engineId ? previous : undefined),
  });

  if (fleet.error) {
    return (
      <main className="page-message">
        <h1>The analysis service is not reachable</h1>
        <p>Start it from the project root with <code>uvicorn api.main:app</code>, then reload this page.</p>
        <ErrorNote error={fleet.error} />
      </main>
    );
  }

  return (
    <main className="workspace">
      <EngineExplorer datasets={datasets.data?.datasets} engines={fleet.data?.engines} />
      <section className="centre" aria-label="3D engine">
        <div className="scene-title">
          <h1>{facts.data?.engine ?? `Engine ${engineId}`}</h1>
          {facts.data && <span>{facts.data.estimate_cycles} flights estimated · range {rangeText(facts.data)}</span>}
        </div>
        <EngineScene facts={facts.data} history={history.data} sensors={sensors.data?.sensors} />
      </section>
      <IntelligencePanel facts={facts.data} loading={facts.isLoading} error={facts.error}
                         onDownload={() => { window.location.href = `/api/engines/${engineId}/report${cycle === null ? "" : `?cycle=${cycle}`}`; }} />
      <HistoryPanel history={history.data} facts={facts.data} sensors={sensors.data?.sensors} />
    </main>
  );
}

export default function App() {
  return (
    <div className="app">
      <TopNav />
      <Routes>
        <Route path="/" element={<Navigate to="/engine" replace />} />
        {sections().map((s) => <Route key={s.path} path={s.path} element={s.element} />)}
        <Route path="*" element={<Navigate to="/engine" replace />} />
      </Routes>
    </div>
  );
}
