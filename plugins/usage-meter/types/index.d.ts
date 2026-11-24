export type Limit = { kind: string; percentUsed: number; resetsAt?: string };

export type Reading = { tokens?: number; window: number; percent?: number; limits: Limit[] };

export type Held = { text: string; idleMs: number; tokens: number };

/** The /keepwarm switch: whether it is on, pings since the last real turn, and why it last stopped ('' = none). */
export type KeepWarm = { isOn: boolean; pings: number; error: string };

declare module "claude-code" {
  interface PluginState {
    "usage-meter": {
      reading: Reading | null;
      lastTurnEnd: number | null;
      held: Held | null;
      now: number;
      okUntil: number;
      keepWarm: KeepWarm;
    };
  }
}
