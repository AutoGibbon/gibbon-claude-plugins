import { expect, mock, test } from "claude-code/testing";

const START = 1_000_000_000;
const MIN = 60_000;

const BAND = {
  plugin: "usage-meter",
  component: "AbovePrompt",
  requestId: "usage-meter",
  props: {
    hasSurvey: false,
    isCollapsed: false,
    isWorking: false,
    maxRows: 8,
    bodyColumns: 120,
    scroll: { offset: 0, bodyRows: 7 },
    view: {},
  },
} as const;

const USAGE = { context: { tokens: 50_000, window: 200_000, percent: 25 }, rateLimits: [] };

function setUp(on: Parameters<Parameters<typeof test>[1]>[1], fork: () => unknown) {
  const clock = mock.clock(on, { now: START });
  mock.store(on, { lastTurnEnd: { s1: START } });
  const forks: string[] = [];
  on("session.id", () => ({ value: "s1" }));
  on("session.usage", () => ({ value: USAGE }));
  on("command.register", () => ({ value: { command: "keepwarm" } }));
  on("session.start", (_, e) => ({ cwd: e.cwd }));
  on("ui.toast", () => ({ value: undefined }));
  on("model.fork", (_, e) => {
    forks.push(e.prompt);
    return { value: fork() };
  });
  return { clock, forks };
}

const HIT = {
  isAnswered: true,
  text: "ok",
  usage: { input_tokens: 10, output_tokens: 1, cache_read_input_tokens: 50_000, cache_creation_input_tokens: 0 },
};

test("keep-warm pings once in the window before expiry and the band shows the next ping", async ($, on) => {
  const { clock, forks } = setUp(on, () => HIT);
  await $.session.start({ cwd: "/", surface: "terminal", isInteractive: true });
  await $.command.run({ command: "keepwarm", args: "on" });

  await clock.advance(51 * MIN);
  expect(forks.length).toBe(0);
  await clock.advance(1.5 * MIN);
  expect(forks.length).toBe(1);
  await clock.advance(2 * MIN);
  expect(forks.length).toBe(1);

  for (const surface of ["terminal", "desktop"] as const) {
    const ui = await $.ui.mount({ ...BAND, surface });
    expect((await ui.find({ type: "Text", text: /warm \d+m left, ping .*\(1\)/ }))?.text).toMatch(/warm 5\dm left/);
    await ui.unmount();
  }
});

test("keep-warm off never pings", async ($, on) => {
  const { clock, forks } = setUp(on, () => HIT);
  await $.session.start({ cwd: "/", surface: "terminal", isInteractive: true });

  await clock.advance(55 * MIN);
  expect(forks.length).toBe(0);
});

test("a ping that finds the cache cold stops keep-warm and says so", async ($, on) => {
  const cold = { ...HIT, usage: { ...HIT.usage, cache_read_input_tokens: 0, cache_creation_input_tokens: 50_000 } };
  const { clock, forks } = setUp(on, () => cold);
  await $.session.start({ cwd: "/", surface: "terminal", isInteractive: true });
  await $.command.run({ command: "keepwarm", args: "on" });

  await clock.advance(53 * MIN);
  await clock.advance(60 * MIN);
  expect(forks.length).toBe(1);

  const ui = await $.ui.mount({ ...BAND, surface: "terminal" });
  expect((await ui.find({ type: "Text", text: /keep-warm stopped/ }))?.text).toMatch(/keep-warm stopped: the cache was already cold$/);
  await ui.unmount();
});
