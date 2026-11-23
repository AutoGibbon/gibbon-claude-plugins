/** One background task still in flight, as the band lists it. */
export type TaskRow = { id: string; type: string; description: string };

/** One subagent or teammate as `$.agent.list()` last gave it, kept after the engine drops it. */
export type AgentRow = {
  id: string;
  /** The engine's task kind; absent on rows stored before it was kept, which are subagents. */
  kind?: "local_agent" | "in_process_teammate";
  description: string;
  model?: string;
  status: string;
  startedAt: number;
  tokens: number;
  usd?: number;
};

/** Every subagent seen this session, and when they were last read. */
export type AgentBoard = { at: number; rows: AgentRow[] };

/** One prompt the session has scheduled: a cron job, or the pending wake-up of a dynamic /loop. */
export type ScheduledRow = {
  id: string;
  description: string;
  /** The scheduler's own wording of when it runs; absent for a wake-up. */
  humanSchedule?: string;
  /** Epoch milliseconds of the next run, when the scheduler gave one. */
  fireAt?: number;
  recurring: boolean;
};

declare module "claude-code" {
  interface PluginState {
    "bg-tasks": { tasks: TaskRow[]; agents: Shaped<AgentBoard>; schedule: ScheduledRow[] };
  }
}
