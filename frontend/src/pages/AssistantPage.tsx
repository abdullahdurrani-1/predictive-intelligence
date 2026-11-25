import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, post, rangeText, STATUS_COLOUR } from "../api";
import { ErrorNote, Skeleton } from "../components/panels";
import { useApp, type ChatTurn } from "../store";

interface ChatReply {
  answer: string;
  source: string;
  note: string;
  engine_id: number;
  evidence: { tool: string; arguments: Record<string, number>; result: Record<string, unknown> }[];
}

const SUGGESTIONS = [
  "Can you explain the current condition of this engine in simple language?",
  "How much useful life might remain?",
  "Why do you think this engine is deteriorating?",
  "Which sensors are responsible for this prediction?",
  "What does sensor 11 mean?",
  "Why is this prediction uncertain?",
  "What should the maintenance team investigate?",
  "Compare this engine with engine 54",
];

const TOOL_LABEL: Record<string, string> = {
  get_engine_summary: "Engine summary", predict_remaining_useful_life: "Remaining-life estimate",
  get_prediction_uncertainty: "Prediction range", explain_prediction: "Model explanation",
  get_sensor_history: "Sensor history", explain_sensor: "Sensor reference", compare_engines: "Engine comparison",
  get_model_information: "Model information",
};

export function AssistantPage() {
  const { engineId, cycle, selectEngine, conversations, addTurn, clearConversation, plainLanguage, setPlainLanguage } = useApp();
  const [draft, setDraft] = useState("");
  const [useModel, setUseModel] = useState(true);
  const [copied, setCopied] = useState<number | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const turns = conversations[engineId] ?? [];

  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet });
  const facts = useQuery({ queryKey: ["engine", engineId, cycle], queryFn: () => api.engine(engineId, cycle) });
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api.settings() });

  const send = useMutation({
    // The engine is fixed when the question is sent, so a reply can never be filed under a different engine.
    mutationFn: (question: string) => post<ChatReply>("/assistant/chat", {
      engine_id: engineId, cycle, plain_language: plainLanguage, use_language_model: useModel,
      messages: [...turns.map(({ role, content }) => ({ role, content })), { role: "user", content: question }],
    }),
    onSuccess: (reply) => addTurn(reply.engine_id, { role: "assistant", content: reply.answer, source: reply.source, note: reply.note, evidence: reply.evidence }),
  });

  const ask = (question: string) => {
    const text = question.trim();
    if (!text || send.isPending) return;
    addTurn(engineId, { role: "user", content: text });
    setDraft("");
    send.mutate(text);
  };
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length, send.isPending]);

  const copy = async (index: number, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(index);
    setTimeout(() => setCopied(null), 1500);
  };
  const assistant = settings.data?.assistant;

  return (
    <main className="page assistant-page">
      <section className="card chat">
        <div className="card-head">
          <div>
            <h1>AI Assistant</h1>
            <p className="hint">Asking about <strong>Engine {engineId}</strong>{cycle ? ` as of flight ${cycle}` : " at its latest recorded flight"}. Each engine has its own conversation.</p>
          </div>
          <div className="chat-options">
            <label className="inline">Engine
              <select value={engineId} onChange={(e) => selectEngine(Number(e.target.value))}>
                {fleet.data?.engines.map((e) => <option key={e.engine_id} value={e.engine_id}>Engine {e.engine_id}</option>)}
              </select>
            </label>
            <label className="switch" title="Avoids technical terms and explains with everyday comparisons">
              <input type="checkbox" checked={plainLanguage} onChange={(e) => setPlainLanguage(e.target.checked)} />
              Explain like I'm new to aviation
            </label>
            <label className="switch" title="When off, answers come from the built-in rule-based layer">
              <input type="checkbox" checked={useModel} onChange={(e) => setUseModel(e.target.checked)} />
              Use language model
            </label>
            <button onClick={() => clearConversation(engineId)} disabled={turns.length === 0}>Clear</button>
          </div>
        </div>

        <div className="messages" aria-live="polite">
          {turns.length === 0 && (
            <div className="empty">
              <p>Ask about this engine in ordinary language. The assistant can only use what the prediction system returns for the engine, and shows that evidence under every answer.</p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => <button key={s} onClick={() => ask(s)}>{s}</button>)}
              </div>
            </div>
          )}
          {turns.map((turn: ChatTurn, index) => (
            <article key={index} className={`message ${turn.role}`}>
              <div className="who">{turn.role === "user" ? "You" : "Assistant"}</div>
              <div className="bubble">
                {turn.content.split("\n").map((line, i) => line.trim() ? <p key={i}>{line}</p> : null)}
                {turn.role === "assistant" && (
                  <footer>
                    <span className="source">Written by: {turn.source}{turn.note ? ` · ${turn.note}` : ""}</span>
                    <button onClick={() => copy(index, turn.content)}>{copied === index ? "Copied" : "Copy"}</button>
                    {turn.evidence && turn.evidence.length > 0 && (
                      <details>
                        <summary>Evidence used ({turn.evidence.length} {turn.evidence.length === 1 ? "lookup" : "lookups"})</summary>
                        {turn.evidence.map((item, i) => (
                          <div key={i} className="evidence">
                            <strong>{TOOL_LABEL[item.tool] ?? item.tool}</strong>
                            <span className="hint">{Object.entries(item.arguments).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ") || "no parameters"}</span>
                            <pre>{JSON.stringify(item.result, null, 1)}</pre>
                          </div>
                        ))}
                      </details>
                    )}
                  </footer>
                )}
              </div>
            </article>
          ))}
          {send.isPending && (
            <article className="message assistant">
              <div className="who">Assistant</div>
              <div className="bubble"><Skeleton lines={3} /><span className="hint">Looking up this engine's results and checking the answer against them. This can take up to a minute.</span></div>
            </article>
          )}
          {send.error && <ErrorNote error={send.error} />}
          <div ref={end} />
        </div>

        {turns.length > 0 && (
          <div className="suggestions compact">
            {SUGGESTIONS.slice(0, 5).map((s) => <button key={s} onClick={() => ask(s)} disabled={send.isPending}>{s}</button>)}
          </div>
        )}
        <form className="composer" onSubmit={(event) => { event.preventDefault(); ask(draft); }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={`Ask about Engine ${engineId}…`} aria-label="Your question" maxLength={500} />
          <button type="submit" disabled={!draft.trim() || send.isPending}>Send</button>
        </form>
        <p className="hint">
          {assistant ? (assistant.key_configured
            ? `Language model: ${assistant.provider} (${assistant.model}). Its answer is shown only after every number in it has been found in the evidence; otherwise the built-in rule-based answer is used.`
            : "No language-model key is configured, so answers come from the built-in rule-based layer.") : ""}
          {" "}Answers appear whole, not word by word, because they are checked first.
        </p>
      </section>

      <aside className="card briefing">
        <h2>Maintenance briefing <span className="tag derived">from the model</span></h2>
        {facts.error ? <ErrorNote error={facts.error} /> : !facts.data ? <Skeleton lines={8} /> : (
          <>
            <div className="status" style={{ borderColor: STATUS_COLOUR[facts.data.status.key] }}>
              <strong style={{ color: STATUS_COLOUR[facts.data.status.key] }}>{facts.data.status.label}</strong>
              <span>{facts.data.status.plain}</span>
            </div>
            <a className="link" href={`/api/engines/${engineId}/report${cycle ? `?cycle=${cycle}` : ""}`}>Download report (PDF)</a>
            <h3>Prediction summary</h3>
            <p>About <strong>{facts.data.estimate_cycles}</strong> flights estimated remaining; likely range <strong>{rangeText(facts.data)}</strong> flights, based on {facts.data.cycles_recorded} recorded flights.</p>
            <h3>Important changes</h3>
            <ul className="plain-list">
              {facts.data.main_reasons.map((r) => (
                <li key={r.sensor}>{r.description} ({r.symbol}) is {r.movement} early life: {r.recent_level} against {r.early_life_level} {r.unit}.</li>
              ))}
            </ul>
            <h3>Suggested areas for further investigation</h3>
            <p>{facts.data.status.consider}</p>
            <p>A reviewer could start with the recorded trends of the measurements listed above, and confirm the sensors themselves are reading correctly: a faulty sensor can make the estimate too optimistic.</p>
            <h3>Uncertainty and limits</h3>
            <ul className="plain-list">{facts.data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            <p className="hint">Status and suggestions: {facts.data.status.basis}. The measurements listed are what the model relied on, not a diagnosed fault.</p>
          </>
        )}
      </aside>
    </main>
  );
}
