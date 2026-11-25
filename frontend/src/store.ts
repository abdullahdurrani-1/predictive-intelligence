import { create } from "zustand";

export type ViewMode = "overview" | "components" | "sensors" | "health";
export type ComponentKey = "fan" | "lpc" | "hpc" | "combustor" | "hpt" | "lpt" | "nozzle";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  source?: string;
  note?: string;
  evidence?: { tool: string; arguments: Record<string, number>; result: Record<string, unknown> }[];
}

interface AppState {
  engineId: number;
  /** Flight being inspected. null means the engine's last recorded flight. */
  cycle: number | null;
  viewMode: ViewMode;
  component: ComponentKey | null;
  paused: boolean;
  cutaway: boolean;
  /** One conversation per engine, so answers about one engine never mix with another. */
  conversations: Record<number, ChatTurn[]>;
  plainLanguage: boolean;
  addTurn: (engineId: number, turn: ChatTurn) => void;
  clearConversation: (engineId: number) => void;
  setPlainLanguage: (value: boolean) => void;
  selectEngine: (id: number) => void;
  selectCycle: (cycle: number | null) => void;
  setViewMode: (mode: ViewMode) => void;
  selectComponent: (component: ComponentKey | null) => void;
  togglePaused: () => void;
  toggleCutaway: () => void;
}

export const useApp = create<AppState>((set) => ({
  engineId: 37,
  cycle: null,
  viewMode: "overview",
  component: null,
  paused: false,
  cutaway: true,
  conversations: {},
  plainLanguage: false,
  addTurn: (engineId, turn) => set((state) => ({
    conversations: { ...state.conversations, [engineId]: [...(state.conversations[engineId] ?? []), turn] },
  })),
  clearConversation: (engineId) => set((state) => ({ conversations: { ...state.conversations, [engineId]: [] } })),
  setPlainLanguage: (plainLanguage) => set({ plainLanguage }),
  // A new engine always opens at its latest flight, so one engine's selected flight never leaks into another.
  selectEngine: (engineId) => set({ engineId, cycle: null }),
  selectCycle: (cycle) => set({ cycle }),
  setViewMode: (viewMode) => set({ viewMode, component: null }),
  selectComponent: (component) => set({ component }),
  togglePaused: () => set((state) => ({ paused: !state.paused })),
  toggleCutaway: () => set((state) => ({ cutaway: !state.cutaway })),
}));
