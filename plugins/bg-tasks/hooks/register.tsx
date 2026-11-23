import { atom, read, update } from "claude-code";
import type { EngineInterface, Register, Timer, ToolResultOf } from "claude-code";

import type { AgentRow, ScheduledRow, TaskRow } from "../types";

const tasks = atom({ plugin: "bg-tasks", key: "tasks" } as const, [] as TaskRow[]);
const schedule = atom({ plugin: "bg-tasks", key: "schedule" } as const, [] as ScheduledRow[]);
const agents = atom({ plugin: "bg-tasks", key: "agents" } as const, { at: 0, rows: [] }, { shape: "agents-1" });

const MAX_LISTED = 3;
// The band's name for each task type, from `background_tasks` (`shell`, `subagent`) or a `tool.call` (`Bash`).
const KIND: Record<string, string> = { Bash: "bash", shell: "bash", Agent: "agent", subagent: "agent" };
// Lichen theme accents as their nearest xterm-256 slot, so the terminal and VS Code draw the same colour.
const KIND_COLOR: Record<string, string> = {
  agent: "#8787af", // 103, lavender
  bash: "#af875f", // 137, amber
  monitor: "#5f8787", // 66, teal
  workflow: "#5f875f", // 65, sage
  "mcp task": "#00875f", // 29, green
  teammate: "#87875f", // 101, ochre
  // Bright accents, whose nearest slot the base accents above don't already take.
  "cloud session": "#5fafaf", // 73, bright blue
  dream: "#af87af", // 139, bright magenta
  "memory save": "#87af87", // 108, bright cyan
  "auto-mode scan": "#5faf87", // 72, bright green
  scheduled: "#878787", // 102, bright white
};
// The id of the one pending wake-up a dynamic /loop holds; ScheduleWakeup returns none of its own.
const WAKEUP = "wakeup";

/** One band line, one value per grid column; an empty string leaves its cell blank. */
type Line = { kind: string; task: string; tokens: string; usd: string; model: string; time: string };
type Column = Exclude<keyof Line, "kind" | "task">;
const FIGURES: Column[] = ["tokens", "usd", "model", "time"];
const LIVE = new Set(["pending", "running", "waiting"]);
// Task types `$.agent.list()` also reports; the band lists those from `agents`, with live figures.
const AGENT_TYPES = new Set(["subagent", "Agent", "teammate"]);

// Module variables reset on a reload; session.start polls once and restarts the ticker if an agent is live.
let ticker: Timer | undefined;
let keepUntil = 0;

type Summary = { id: string; type: string; description: string; command?: string };

/** Convert the engine's `background_tasks` list into band rows. */
const toRows = (list: readonly Summary[] | undefined): TaskRow[] =>
  (list ?? []).map((t) => ({ id: t.id, type: t.type, description: t.description || t.command || t.id }));

/** Add `row` to `tasks`, replacing any row with its `id`. */
const addTask = ($: EngineInterface, row: TaskRow) =>
  update($, tasks, (list) => [...list.filter((t) => t.id !== row.id), row]);

/** Name a scheduled prompt by its text, or "autonomous loop" for /loop's `<<autonomous-loop…>>` sentinels. */
const promptName = (prompt: string | undefined) =>
  prompt === undefined || prompt.startsWith("<<autonomous-loop") ? "autonomous loop" : prompt;

/** Format epoch milliseconds `at` as local `HH:MM`. */
function clockTime(at: number) {
  const d = new Date(at);

  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function duration(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  const ss = String(s % 60).padStart(2, "0");
  if (m < 60) return `${m}:${ss}`;

  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${ss}`;
}

function tokens(n: number) {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`;

  return `${(n / 1_000_000).toFixed(1)}M`;
}

function family(model: string | undefined) {
  const name = (model ?? "").toLowerCase();

  return ["opus", "sonnet", "haiku", "fable"].find((one) => name.includes(one)) ?? model ?? "";
}

/** Read `$.agent.list()` into `agents`, and run the 1 s ticker only while a subagent is live or one was just spawned. */
async function poll($: EngineInterface) {
  const now = await $.clock.now();
  const list = await $.agent.list();
  const seen = new Set(list.map((one) => one.id));

  await update($, agents, (prev) => {
    // The engine drops finished agents from its list; one dropped while live is closed here.
    const rows = prev.rows.map((row) =>
      !seen.has(row.id) && LIVE.has(row.status) ? { ...row, status: "completed" } : row,
    );
    for (const agent of list) {
      const row: AgentRow = {
        id: agent.id,
        kind: agent.kind,
        description: agent.description,
        model: agent.model,
        status: agent.status,
        startedAt: agent.startTime,
        tokens: agent.tokenCount,
        usd: agent.cost?.usd,
      };
      const at = rows.findIndex((one) => one.id === agent.id);
      if (at >= 0) rows[at] = row;
      else rows.push(row);
    }

    return { at: now, rows: rows.slice(-30) };
  });

  if (list.some((one) => LIVE.has(one.status)) || now < keepUntil) {
    ticker ??= $.clock.every(1000, () => void poll($).catch(() => undefined));
  } else if (ticker !== undefined) {
    ticker.cancel();
    ticker = undefined;
  }
}

export const register: Register = (on) => {
  on("session.start", async ($, e, next) => {
    const started = await next(e);
    await poll($);

    return started;
  });

  // Poll for 10 s even before the new agent is listed, so its first reading isn't missed.
  on("agent.spawn", async ($, e, next) => {
    keepUntil = (await $.clock.now()) + 10_000;
    ticker ??= $.clock.every(1000, () => void poll($).catch(() => undefined));

    return next(e);
  });

  // Stop and SubagentStop carry the engine's full list of in-flight work, so each replaces the band's list.
  on("classic.Stop", async ($, e, next) => {
    await update($, tasks, () => toRows(e.background_tasks));

    return next(e);
  });

  on("classic.SubagentStop", async ($, e, next) => {
    await update($, tasks, () => toRows(e.background_tasks));

    return next(e);
  });

  // Show a background launch mid-turn, before the turn's Stop reports the authoritative list, and track the
  // prompts the session has scheduled, which no task list reports.
  on("tool.call", async ($, e, next) => {
    const result = await next(e);
    if (result.deny !== undefined || result.isError === true) return result;

    if (e.tool === "Bash") {
      // Set however the command reached the background: run_in_background, Ctrl+B or its timeout.
      const id = (result.result as ToolResultOf<"Bash">).backgroundTaskId;
      if (id !== undefined) await addTask($, { id, type: "shell", description: e.description || e.command });
    } else if (e.tool === "Monitor") {
      const id = (result.result as ToolResultOf<"Monitor">).taskId;
      await addTask($, { id, type: "monitor", description: e.description });
    } else if (e.tool === "ScheduleWakeup") {
      const out = result.result as ToolResultOf<"ScheduleWakeup">;
      const row: ScheduledRow = {
        id: WAKEUP,
        description: promptName(e.prompt),
        fireAt: out.scheduledFor,
        recurring: false,
      };
      await update($, schedule, (rows) => [...rows.filter((one) => one.id !== WAKEUP), ...(out.stopped ? [] : [row])]);
    } else if (e.tool === "CronCreate") {
      const out = result.result as ToolResultOf<"CronCreate">;
      const row: ScheduledRow = {
        id: out.id,
        description: promptName(e.prompt),
        humanSchedule: out.humanSchedule,
        fireAt: out.nextFireAt,
        recurring: out.recurring,
      };
      await update($, schedule, (rows) => [...rows.filter((one) => one.id !== out.id), row]);
    } else if (e.tool === "CronDelete") {
      const out = result.result as ToolResultOf<"CronDelete">;
      await update($, schedule, (rows) =>
        rows.filter((one) => one.id !== e.id && !(out.endedLoopWakeup === true && one.id === WAKEUP)),
      );
    } else if (e.tool === "CronList") {
      // The scheduler's list replaces every cron row; the wake-up stays unless a job fires at the same moment.
      const jobs = (result.result as ToolResultOf<"CronList">).jobs;
      await update($, schedule, (rows) => [
        ...rows.filter((one) => one.id === WAKEUP && !jobs.some((job) => job.nextFireAt === one.fireAt)),
        ...jobs.map((job) => ({
          id: job.id,
          description: promptName(job.prompt),
          humanSchedule: job.humanSchedule,
          fireAt: job.nextFireAt,
          recurring: job.recurring ?? true,
        })),
      ]);
    }

    return result;
  });

  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    const list = (await read($, tasks)).filter((t) => !AGENT_TYPES.has(t.type));
    const board = await read($, agents);
    const live = board.rows.filter((row) => LIVE.has(row.status));
    const now = await $.clock.now();
    // A one-shot job or wake-up past its fire time has fired; a recurring job stays until it is deleted.
    const pending = (await read($, schedule)).filter(
      (row) => row.recurring || row.fireAt === undefined || row.fireAt > now,
    );
    const running = list.length + live.length;

    if (e.props.hasSurvey || running + pending.length === 0) {
      return next(e);
    }

    const { Box, Text } = $.ui.resolve(e);
    const lines: Line[] = [
      ...live.map((row) => ({
        kind: row.kind === "in_process_teammate" ? "teammate" : "agent",
        task: row.description,
        tokens: tokens(row.tokens),
        usd: row.usd === undefined ? "" : `$${row.usd.toFixed(2)}`,
        model: family(row.model),
        time: duration(board.at - row.startedAt),
      })),
      ...list.map((t) => ({
        kind: KIND[t.type] ?? t.type.toLowerCase(),
        task: t.description,
        tokens: "",
        usd: "",
        model: "",
        time: "",
      })),
      ...pending.map((row) => ({
        kind: "scheduled",
        task: row.description,
        tokens: "",
        usd: "",
        model: "",
        time: row.humanSchedule ?? (row.fireAt === undefined ? "" : `at ${clockTime(row.fireAt)}`),
      })),
    ];
    const header = [running > 0 ? `${running} running` : "", pending.length > 0 ? `${pending.length} scheduled` : ""]
      .filter((part) => part !== "")
      .join(", ");
    const shown = lines.slice(0, MAX_LISTED);
    const width = (column: keyof Line) => Math.max(...shown.map((line) => line[column].length));
    // A figure column no shown line fills is left out, so a bash-only band ends after the task.
    const figures = FIGURES.filter((column) => width(column) > 0);
    const extra = lines.length - MAX_LISTED;

    return (
      <Box flexDirection="column" marginTop={1} marginBottom={1}>
        <Text color="yellow">{`● ${header}`}</Text>
        {shown.map((line) => (
          <Box flexDirection="row" width={e.props.bodyColumns} paddingLeft={2} gap={1}>
            <Box width={width("kind")} flexShrink={0}>
              <Text color={KIND_COLOR[line.kind]} dimColor={KIND_COLOR[line.kind] === undefined}>
                {line.kind}
              </Text>
            </Box>
            {/* The task column alone shrinks, so a narrow band cuts the description, not the figures. */}
            <Box width={width("task")} flexShrink={1}>
              <Text dimColor wrap="truncate-end">
                {line.task}
              </Text>
            </Box>
            {figures.map((column) => (
              <Box width={width(column)} flexShrink={0}>
                <Text dimColor>{line[column]}</Text>
              </Box>
            ))}
          </Box>
        ))}
        {extra > 0 ? <Text dimColor>{`  and ${extra} more`}</Text> : null}
      </Box>
    );
  });
};
