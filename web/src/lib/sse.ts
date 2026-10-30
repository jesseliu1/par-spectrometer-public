/**
 * The service's event stream (API-17; 16_ section 5), read with fetch: EventSource cannot send the token in a header
 * and the token must never go into an address (logs, history).
 *
 * `SseParser` turns text chunks into messages as the SSE format says: lines end in LF, CRLF or CR; a blank line ends
 * a message; ":" starts a comment (the service's ": connected"); several `data:` lines join with LF; a message
 * without data is dropped. Events are hints: the page reads the state again after each (re)connection, and keeps
 * what it shows while the stream is down (R-1-5, 16_ section 6 "服务与页面断开").
 */
import type { ServiceEvent } from "../api/types";

export class SseParser {
  private buffer = "";
  private id: string | null = null;
  private name = "";
  private data: string[] = [];

  /** Feed a chunk; returns the messages it completed. */
  push(chunk: string): ServiceEvent[] {
    this.buffer += chunk;
    const done: ServiceEvent[] = [];
    for (;;) {
      const match = /\r\n|\r|\n/.exec(this.buffer);
      if (match === null) break;
      // a CR at the very end may be the first half of CRLF: wait for the next chunk
      if (match[0] === "\r" && match.index === this.buffer.length - 1) break;
      const line = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      const event = this.line(line);
      if (event !== null) done.push(event);
    }
    return done;
  }

  private line(line: string): ServiceEvent | null {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return null;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.name = value;
    else if (field === "data") this.data.push(value);
    else if (field === "id") this.id = value;
    return null;
  }

  private dispatch(): ServiceEvent | null {
    const name = this.name || "message";
    const data = this.data;
    const id = this.id;
    this.name = "";
    this.data = [];
    this.id = null;
    if (data.length === 0) return null;
    let parsed: unknown;
    try {
      parsed = JSON.parse(data.join("\n"));
    } catch {
      parsed = { text: data.join("\n") };
    }
    const numeric = id === null ? null : Number(id);
    return {
      id: numeric !== null && Number.isFinite(numeric) ? numeric : null,
      name,
      data: typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : { value: parsed },
    };
  }
}

export type StreamState = "connecting" | "open" | "reconnecting" | "closed";

export interface EventStreamOptions {
  /** opens the stream (ApiClient.openEvents) */
  open: (signal: AbortSignal) => Promise<ReadableStream<Uint8Array>>;
  onEvent: (event: ServiceEvent) => void;
  /** called with "open" after every (re)connection: the page then reads the state again */
  onState: (state: StreamState) => void;
  /** wait before reconnecting (doubles up to maxDelayMs) */
  delayMs?: number;
  maxDelayMs?: number;
  sleep?: (ms: number) => Promise<void>;
}

export interface EventStream {
  close: () => void;
  /** resolves when the loop has ended (after close) */
  done: Promise<void>;
}

/** Reconnect waits (D-214): 1 s, doubling to at most 10 s while the service stays away. */
export const RECONNECT_MS = 1000;
export const RECONNECT_MAX_MS = 10_000;

const wait = (ms: number) => new Promise<void>((wake) => setTimeout(wake, ms));

export function connectEvents(options: EventStreamOptions): EventStream {
  const controller = new AbortController();
  const sleep = options.sleep ?? wait;
  const first = options.delayMs ?? RECONNECT_MS;
  const limit = options.maxDelayMs ?? RECONNECT_MAX_MS;
  let closed = false;

  async function readOnce(opened: () => void): Promise<void> {
    const stream = await options.open(controller.signal);
    opened();
    options.onState("open");
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    const parser = new SseParser();
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const event of parser.push(decoder.decode(value, { stream: true }))) options.onEvent(event);
      }
    } finally {
      reader.releaseLock();
    }
  }

  async function loop(): Promise<void> {
    let delay = first;
    options.onState("connecting");
    while (!closed) {
      const attempt = { opened: false };
      try {
        await readOnce(() => (attempt.opened = true));
      } catch {
        // the service went away or answered with an error: wait and try again; the page keeps its data
      }
      if (closed) break;
      if (attempt.opened) delay = first;
      options.onState("reconnecting");
      await sleep(delay);
      if (!attempt.opened) delay = Math.min(delay * 2, limit);
    }
    options.onState("closed");
  }

  const done = loop();
  return {
    close: () => {
      closed = true;
      controller.abort();
    },
    done,
  };
}
