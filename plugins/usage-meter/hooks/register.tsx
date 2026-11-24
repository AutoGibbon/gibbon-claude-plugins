import { atom, read, update } from "claude-code";
import type {
  EngineInterface,
  PromptOrigin,
  Register,
  SessionContextUsage,
  SessionRateLimit,
  Timer,
} from "claude-code";

import type { Reading } from "../types";

// On a subscription the prompt cache keeps a chat for about an hour after its
// last request; past that, the next message rereads the whole chat.
const CACHE_MS = 60 * 60 * 1000;
const COLD_TOKENS = 20_000;
// After "Send anyway" the chat is not held again for this long, so the
// prompt it sends (or one another mod rewrites from it) goes through.
const OK_MS = 15 * 60 * 1000;
const STORE_KEY = "lastTurnEnd";
// /keepwarm pings this long before the cache would expire, and never in its last minute, so a cold cache is
// never pinged.
const PING_LEAD_MS = 8 * 60_000;
const PING_MARGIN_MS = 60_000;
const RETRY_MS = 30_000;
// Past this many pings with no real turn between, rewriting the cache once is cheaper than pinging on.
const MAX_PINGS = 20;
// Names no effort and asks for haste, so the fork reads the cached chat on every model.
const PING_PROMPT = 'Keep-warm ping. You have no tools. Reply with just "ok" straight away, without thinking it over.';

const reading = atom({ plugin: "usage-meter", key: "reading" } as const, null);
const lastTurnEnd = atom({ plugin: "usage-meter", key: "lastTurnEnd" } as const, null);
const held = atom({ plugin: "usage-meter", key: "held" } as const, null);
const clockNow = atom({ plugin: "usage-meter", key: "now" } as const, 0);
const okUntil = atom({ plugin: "usage-meter", key: "okUntil" } as const, 0);
const keepWarm = atom({ plugin: "usage-meter", key: "keepWarm" } as const, { isOn: false, pings: 0, error: "" });

let ticker: Timer | undefined;
// When the main thread last sent a request, so a long turn is not pinged mid-way.
let lastStep = 0;
// No ping before this time: set while one is out and after a failure.
let nextTryAt = 0;

function toReading(context: SessionContextUsage, limits: readonly SessionRateLimit[]): Reading {
  return {
    tokens: context.tokens,
    window: context.window,
    percent: context.percent,
    limits: limits.map((one) => ({ kind: one.kind, percentUsed: one.percentUsed, resetsAt: one.resetsAt })),
  };
}

function isPersonsOwn(origin: PromptOrigin) {
  return origin.kind === "composer" || origin.kind === "bridge" || (origin.kind === "plugin" && origin.asUser === true);
}

function size(n: number) {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`;

  return `${(n / 1_000_000).toFixed(1)}M`;
}

function ago(ms: number) {
  const m = Math.max(1, Math.round(ms / 60_000));
  if (m < 60) return `${m}m`;

  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

// The time on this machine's own clock, as "15:10".
function localTime(iso: string) {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "";
  const local = new Date(ms);

  return `${String(local.getHours()).padStart(2, "0")}:${String(local.getMinutes()).padStart(2, "0")}`;
}

function tone(percent: number) {
  if (percent >= 95) return "error";
  if (percent >= 80) return "warning";

  return undefined;
}

async function stamp($: EngineInterface) {
  const now = await $.clock.now();
  await update($, clockNow, () => now);
  await maybePing($, now);
}

async function stopKeepWarm($: EngineInterface, why: string) {
  await update($, keepWarm, () => ({ isOn: false, pings: 0, error: why }));
  $.ui.toast(`Keep-warm stopped: ${why}.`);
}

/** Fork the chat's last request with a one-line prompt when keep-warm is on and the cache is about to expire. */
async function maybePing($: EngineInterface, now: number) {
  const warm = await read($, keepWarm);
  const last = await read($, lastTurnEnd);
  if (!warm.isOn || last === null || now < nextTryAt) return;
  const idle = now - Math.max(last, lastStep);
  if (idle < CACHE_MS - PING_LEAD_MS || idle >= CACHE_MS - PING_MARGIN_MS) return;
  if (warm.pings >= MAX_PINGS) return stopKeepWarm($, `${MAX_PINGS} pings with no reply from you`);

  nextTryAt = now + PING_LEAD_MS;
  const r = await $.model.fork({ prompt: PING_PROMPT });
  if (!r.isAnswered && r.reason === "nothing-to-fork") return stopKeepWarm($, "nothing to ping until the next reply");
  if (!r.isAnswered && (r.reason === "api-error" || r.reason === "aborted")) {
    const status = r.reason === "api-error" ? (r.status ?? 0) : 0;
    // A 4xx other than 429 is refused the same way every time.
    if (status >= 400 && status < 500 && status !== 429) return stopKeepWarm($, `ping failed, HTTP ${status}`);
    nextTryAt = now + RETRY_MS;
    return;
  }
  if (r.usage.cache_read_input_tokens < r.usage.cache_creation_input_tokens) {
    return stopKeepWarm($, "the cache was already cold");
  }
  await update($, keepWarm, (w) => ({ ...w, pings: w.pings + 1 }));
  await remember($, now);
}

async function remember($: EngineInterface, at: number) {
  await update($, lastTurnEnd, () => at);
  const id = await $.session.id();
  const stored = ((await $.store.get(STORE_KEY)) ?? {}) as Record<string, number>;
  const kept = Object.entries({ ...stored, [id]: at })
    .sort((a, b) => b[1] - a[1])
    .slice(0, 40);
  await $.store.set(STORE_KEY, Object.fromEntries(kept));
}

async function sendAnyway($: EngineInterface) {
  const message = await read($, held);
  if (!message) return;
  const now = await $.clock.now();
  await update($, okUntil, () => now + OK_MS);
  await update($, held, () => null);
  await $.prompt.submit({ text: message.text, asUser: true });
}

async function startFresh($: EngineInterface) {
  const message = await read($, held);
  if (!message) return;
  await update($, held, () => null);
  await $.prompt.fill({ text: message.text });
  const commands = await $.command.list();
  if (commands.some((one) => one.name === "handoff")) {
    await $.command.run({ command: "handoff" });
  } else {
    $.ui.toast("Your message is back in the prompt box. Start a new chat and paste it there.");
  }
}

async function cancel($: EngineInterface) {
  const message = await read($, held);
  await update($, held, () => null);
  if (message) await $.prompt.fill({ text: message.text });
}

export const register: Register = (on) => {
  on("session.start", async ($, e, next) => {
    const started = await next(e);
    await $.command.register({
      name: "keepwarm",
      description: "Keep this chat's prompt cache warm while you are away: on, off, or toggle",
      argumentHint: "[on|off]",
      immediate: true,
    });
    const usage = await $.session.usage();
    await update($, reading, () => toReading(usage.context, usage.rateLimits));

    // A resumed chat: when its last reply came is kept across sessions.
    if ((await read($, lastTurnEnd)) === null) {
      const id = await $.session.id();
      const stored = ((await $.store.get(STORE_KEY)) ?? {}) as Record<string, number>;
      const at = stored[id];
      if (typeof at === "number") await update($, lastTurnEnd, () => at);
    }

    ticker?.cancel();
    ticker = $.clock.every(30_000, () => void stamp($));
    await stamp($);

    return started;
  });

  on("session.measure", async ($, e, next) => {
    await update($, reading, () => toReading(e.context, e.rateLimits));

    return next(e);
  });

  on("turn.complete", async ($, e, next) => {
    if (e.agentId === undefined) {
      const now = await $.clock.now();
      await remember($, now);
      await update($, keepWarm, (w) => ({ ...w, pings: 0, error: "" }));
      await stamp($);
    }

    return next(e);
  });

  on("turn.step", async function* ($, e, next) {
    if (e.agentId === undefined) lastStep = await $.clock.now();

    return yield* next(e);
  });

  on("command.run", { command: "keepwarm" }, async ($, e) => {
    const arg = e.args.trim().toLowerCase();
    const was = await read($, keepWarm);
    const isOn = arg === "on" ? true : arg === "off" ? false : arg === "" ? !was.isOn : undefined;
    if (isOn === undefined) return { text: "Usage: /keepwarm [on|off]" };
    nextTryAt = 0;
    await update($, keepWarm, () => ({ isOn, pings: 0, error: "" }));

    return {
      text: isOn
        ? `Keep-warm on: ${PING_LEAD_MS / 60_000} min before the cache would expire it re-reads the chat from cache, up to ${MAX_PINGS} times in a row.`
        : "Keep-warm off.",
    };
  });

  on("prompt.submit", async ($, e, next) => {
    const skips =
      !isPersonsOwn(e.origin) ||
      e.isMeta === true ||
      e.command !== undefined ||
      e.turnId !== undefined ||
      /^\s*go:/i.test(e.text);
    if (skips) return next(e);

    const now = await $.clock.now();
    const last = await read($, lastTurnEnd);
    if (last === null || now < (await read($, okUntil)) || now - last <= CACHE_MS) return next(e);

    const known = (await read($, reading))?.tokens;
    const tokens = known ?? (await $.session.usage({ breakdown: "summary" })).context.breakdown?.totalTokens ?? 0;
    if (tokens < COLD_TOKENS) return next(e);

    // Images can't be held and sent again, so those go through with a note.
    if (e.attachments !== undefined && e.attachments.length > 0) {
      $.ui.toast(`This chat went cold, so this message rereads about ${size(tokens)} tokens.`);

      return next(e);
    }

    await update($, held, () => ({ text: e.text, idleMs: now - last, tokens }));

    return { drop: "Usage Meter: this chat went cold. Check the card above." };
  }).catch(($, e, next) => next(e));

  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    const beneath = await next(e);
    if (e.props.hasSurvey) return beneath;

    const now = await read($, clockNow);
    const last = await read($, lastTurnEnd);
    const meter = await read($, reading);
    const message = await read($, held);
    const warm = await read($, keepWarm);
    if (meter === null && message === null) return beneath;

    const { Box, Button, Text } = $.ui.resolve(e);
    const parts = [];

    if (meter !== null && meter.tokens !== undefined) {
      const percent = meter.percent ?? Math.round((meter.tokens / meter.window) * 100);
      parts.push(<Text color={tone(percent)}>Chat {percent}%</Text>);
      parts.push(
        <Text>
          {size(meter.tokens)}/{size(meter.window)}
        </Text>,
      );
    }
    for (const limit of meter?.limits ?? []) {
      const percent = Math.round(limit.percentUsed);
      if (limit.kind === "five_hour") {
        const resets = limit.resetsAt ? localTime(limit.resetsAt) : "";
        parts.push(
          <Text color={tone(percent)}>
            5hr {percent}%{resets ? `, resets ${resets}` : ""}
          </Text>,
        );
      } else if (limit.kind === "seven_day") {
        parts.push(<Text color={tone(percent)}>week {percent}%</Text>);
      } else {
        parts.push(
          <Text color={tone(percent)}>
            {limit.kind.replace(/_/g, " ")} {percent}%
          </Text>,
        );
      }
    }
    if (e.props.isWorking) {
      parts.push(<Text>warm</Text>);
    } else if (last !== null) {
      const idle = now - last;
      const isBig = (meter?.tokens ?? 0) >= COLD_TOKENS;
      parts.push(
        idle <= CACHE_MS ? (
          <Text>
            warm {Math.max(1, Math.ceil((CACHE_MS - idle) / 60_000))}m left
            {warm.isOn ? `, ping ${localTime(new Date(last + CACHE_MS - PING_LEAD_MS).toISOString())}` : ""}
            {warm.isOn && warm.pings > 0 ? ` (${warm.pings})` : ""}
          </Text>
        ) : (
          <Text color={isBig ? "warning" : undefined}>cold</Text>
        ),
      );
    }
    if (warm.error) parts.push(<Text color="warning">keep-warm stopped: {warm.error}</Text>);

    return (
      <Box flexDirection="column">
        {beneath}
        {message !== null && (
          <Box flexDirection="column" borderStyle="round" borderColor="warning" paddingX={1}>
            <Text>
              This chat went cold {ago(message.idleMs - CACHE_MS)} ago. Sending makes Claude reread about{" "}
              {size(message.tokens)} tokens.
            </Text>
            <Box flexDirection="row" gap={1}>
              <Button key="send-anyway" label="Send anyway" variant="primary" onPress={() => void sendAnyway($)} />
              <Button key="start-fresh" label="Start fresh" onPress={() => void startFresh($)} />
              <Button key="cancel" label="Cancel" onPress={() => void cancel($)} />
            </Box>
          </Box>
        )}
        {parts.length > 0 && (
          <Text dimColor wrap="truncate-end">
            {parts.flatMap((part, i) => (i === 0 ? [part] : [" · ", part]))}
          </Text>
        )}
      </Box>
    );
  });
};
