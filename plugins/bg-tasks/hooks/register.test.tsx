import { expect, test } from "claude-code/testing";

const NOW = 1_000_000_000;

const BAND = {
  plugin: "bg-tasks",
  component: "AbovePrompt",
  requestId: "bg-tasks",
  props: {
    hasSurvey: false,
    isCollapsed: false,
    isWorking: true,
    maxRows: 8,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 7 },
    view: {},
  },
} as const;

test("the band lists a live subagent with figures and a background shell task, on every surface", async ($, on) => {
  on("clock.now", () => ({ value: NOW }));
  on("session.start", (_, e) => ({ cwd: e.cwd }));
  on("tool.call", (_, e) => ({
    result: e.tool === "Bash" ? { stdout: "", stderr: "", interrupted: false, backgroundTaskId: "b1" } : {},
  }));
  on("agent.list", () => ({
    value: [
      {
        id: "a1",
        description: "Run 30s no-op script",
        type: "general-purpose",
        status: "running",
        taskStatus: "running",
        label: "Run 30s no-op script",
        startTime: NOW - 12_000,
        model: "claude-haiku-5-5",
        tokenCount: 3_200,
        cost: { usd: 0.01 },
        hasRow: true,
        kind: "local_agent" as const,
        cwd: "/",
        tokenSamples: [] as number[],
      },
    ],
  }));

  await $.session.start({ cwd: "/", surface: "vscode", isInteractive: true });
  await $.tool.call({ tool: "Bash", command: "python wait.py", description: "Wait 30s", run_in_background: true });

  for (const surface of ["terminal", "desktop", "vscode", "mobile"] as const) {
    const ui = await $.ui.mount({ ...BAND, surface });

    expect((await ui.find({ type: "Text", text: /running$/ }))?.text).toBe("● 2 running");
    for (const text of ["agent", "Run 30s no-op script", "3K", "$0.01", "haiku", "0:12", "bash", "Wait 30s"]) {
      expect((await ui.find({ type: "Text", text }))?.text).toBe(text);
    }
    expect((await ui.find({ type: "Text", text: "agent" }))?.props.color).toBe("#8787af");
    expect((await ui.find({ type: "Text", text: "bash" }))?.props.color).toBe("#af875f");
    expect(await ui.find({ type: "Text", text: /^\.+$/ })).toBeUndefined();
    await ui.unmount();
  }
});

test("a running teammate is listed once, from the agent list, and engine-only task types are coloured", async ($, on) => {
  on("clock.now", () => ({ value: NOW }));
  on("session.start", (_, e) => ({ cwd: e.cwd }));
  on("classic.Stop", () => ({}));
  on("agent.list", () => ({
    value: [
      {
        id: "t1",
        description: "Review the parser",
        type: "reviewer",
        status: "running",
        taskStatus: "running",
        label: "Review the parser",
        startTime: NOW - 5_000,
        model: "claude-sonnet-5-5",
        tokenCount: 900,
        hasRow: true,
        kind: "in_process_teammate" as const,
        cwd: "/",
        tokenSamples: [] as number[],
      },
    ],
  }));

  await $.session.start({ cwd: "/", surface: "terminal", isInteractive: true });
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [
      { id: "t1", type: "teammate", status: "running", description: "Review the parser" },
      { id: "d1", type: "dream", status: "running", description: "Consolidate memories" },
      { id: "c1", type: "cloud session", status: "running", description: "Fix flaky test" },
    ],
  });

  const ui = await $.ui.mount({ ...BAND, surface: "terminal" });
  expect((await ui.find({ type: "Text", text: /running$/ }))?.text).toBe("● 3 running");
  expect(await ui.findAll({ type: "Text", text: "Review the parser" })).toHaveLength(1);
  expect((await ui.find({ type: "Text", text: "teammate" }))?.props.color).toBe("#87875f");
  expect((await ui.find({ type: "Text", text: "dream" }))?.props.color).toBe("#af87af");
  expect((await ui.find({ type: "Text", text: "cloud session" }))?.props.color).toBe("#5fafaf");
  expect(await ui.find({ type: "Text", text: "agent" })).toBeUndefined();
  await ui.unmount();
});

test("a Ctrl+B shell, a monitor, a wake-up and a cron job are listed mid-turn; deleting the job drops it", async ($, on) => {
  on("clock.now", () => ({ value: NOW }));
  on("session.start", (_, e) => ({ cwd: e.cwd }));
  on("agent.list", () => ({ value: [] }));
  on("tool.call", (_, e) => {
    switch (e.tool) {
      case "Bash":
        return {
          result: { stdout: "", stderr: "", interrupted: false, backgroundTaskId: "b2", backgroundedByUser: true },
        };
      case "Monitor":
        return { result: { taskId: "m1", timeoutMs: 300_000 } };
      case "ScheduleWakeup":
        return e.stop === true
          ? {
              result: {
                scheduledFor: 0,
                clampedDelaySeconds: 0,
                wasClamped: false,
                stopped: true,
                cancelledWakeups: 1,
              },
            }
          : { result: { scheduledFor: NOW + 600_000, clampedDelaySeconds: 600, wasClamped: false } };
      case "CronCreate":
        return { result: { id: "c9", humanSchedule: "every 5 minutes", recurring: true, nextFireAt: NOW + 60_000 } };
      case "CronDelete":
        return { result: { id: "c9" } };
      default:
        return { result: {} };
    }
  });

  await $.session.start({ cwd: "/", surface: "terminal", isInteractive: true });
  await $.tool.call({ tool: "Bash", command: "npm run build", description: "Build the app" });
  await $.tool.call({ tool: "Monitor", description: "Watch the deploy", timeout_ms: 300_000, command: "tail -f log" });
  await $.tool.call({ tool: "ScheduleWakeup", delaySeconds: 600, reason: "CI takes ~10 min", prompt: "check CI" });
  await $.tool.call({ tool: "CronCreate", cron: "*/5 * * * *", prompt: "<<autonomous-loop>>" });

  const at = new Date(NOW + 600_000);
  const wake = `at ${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  let ui = await $.ui.mount({ ...BAND, surface: "terminal" });
  expect((await ui.find({ type: "Text", text: /^● / }))?.text).toBe("● 2 running, 2 scheduled");
  for (const text of ["bash", "Build the app", "monitor", "Watch the deploy", "check CI", wake]) {
    expect((await ui.find({ type: "Text", text }))?.text).toBe(text);
  }
  expect((await ui.find({ type: "Text", text: /^scheduled$/ }))?.props.color).toBe("#878787");
  await ui.unmount();

  await $.tool.call({ tool: "CronDelete", id: "c9" });
  await $.tool.call({ tool: "ScheduleWakeup", stop: true });
  ui = await $.ui.mount({ ...BAND, surface: "terminal" });
  expect((await ui.find({ type: "Text", text: /^● / }))?.text).toBe("● 2 running");
  expect(await ui.find({ type: "Text", text: /^scheduled$/ })).toBeUndefined();
  await ui.unmount();
});
