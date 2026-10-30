/**
 * State of the spectrum calculation page (光谱计算; docs/design/ui-v2-pages.md 2.4; API-11..14, API-24, API-25).
 *
 * The service lists the sources and records, finds the nearest record, draws nothing but computes everything (A/B
 * values, the common axis, the time difference, the result, its axis and the plotted ratio points) with V1.0.3's
 * code. This store only follows the V1.0.3 page's selection rules (MainWindow._operation_a_changed and friends):
 *   * A and B each pick a source (an imported position) and a record; the top bar's device is not involved
 *     (UI-159, UI-165, UI-254). At first A takes the first source and B the second (UI-156).
 *   * With "B 匹配 A 的最近时间" on (the default, UI-195), the first visit, a change of A (source or record), a
 *     change of B's source and switching the option back on pick B's record nearest in time to A (UI-163, UI-201,
 *     UI-202, UI-203). Picking B by hand changes nothing on A (UI-205).
 *   * Swapping exchanges sources and records exactly and does not match (UI-186).
 *   * Any change of A, B, the operation or the option drops the result: it must be calculated again (UI-158,
 *     UI-164, UI-187, UI-266).
 *   * A refresh (page shown again, a new import) keeps the selected records while they still exist, and then
 *     keeps the result too (UI-204, UI-267); a source re-imported meanwhile drops the result (D-208).
 * A failed request keeps what is shown and offers a retry (R-1-5). The export uses the result on screen, not the
 * current selection (EXP-022).
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type {
  ExportKind,
  OperationCandidate,
  OperationCandidates,
  OperationComputation,
  OperationExported,
  OperationInputs,
  OperationKey,
  OperationPage,
  OperationSources,
  SourceRef,
} from "../api/types";
import { createResource, invalidate, reset, run, type Resource } from "../lib/resource";

export type SideKey = "a" | "b";

export interface Side {
  /** the source whose records are listed (set only once its list has loaded) */
  source: string | null;
  records: Resource<OperationCandidates>;
  selected: number | null;
  /** a record outside the list (an older nearest match), shown after the list like V1.0.3 adds it */
  extra: OperationCandidate | null;
  /** the nearest-time search found nothing: the list shows only 无可用光谱 (V1.0.3 clears the combo) */
  blank: boolean;
}

export interface CalcPageState {
  page: Resource<OperationPage>;
  sources: Resource<OperationSources>;
  a: Side;
  b: Side;
  autoMatch: boolean;
  operation: OperationKey;
  match: Resource<null>;
  inputs: Resource<OperationInputs>;
  compute: Resource<OperationComputation>;
  /** the calculated result on screen, null until 执行计算 and after any change */
  result: OperationComputation | null;
  exporting: Resource<OperationExported>;
  started: boolean;
}

export type CalcStore = ReturnType<typeof createCalcStore>;

function side(): Side {
  return { source: null, records: createResource<OperationCandidates>(), selected: null, extra: null, blank: false };
}

/** The records a side lists: the service's list, then the extra record when it is not in it (UI-204). */
export function options(entry: Side): OperationCandidate[] {
  if (entry.blank || entry.records.data === null) return [];
  const items = entry.records.data.items;
  if (entry.extra !== null && !items.some((item) => item.id === entry.extra?.id)) return [...items, entry.extra];
  return items;
}

export function selectedCandidate(entry: Side): OperationCandidate | null {
  return options(entry).find((item) => item.id === entry.selected) ?? null;
}

/** The reference sent to the service: position, record id and the database the list came from (D-208). */
export function refOf(entry: Side): SourceRef | null {
  if (entry.source === null || entry.selected === null || entry.records.data === null) return null;
  return { source: entry.source, id: entry.selected, snapshot_id: entry.records.data.snapshot_id };
}

function sameRef(shown: { source: string | null; id: number | null }, wanted: SourceRef | null): boolean {
  return wanted !== null && shown.source === wanted.source && shown.id === wanted.id;
}

export function createCalcStore(api: ApiClient) {
  const state: CalcPageState = reactive({
    page: createResource<OperationPage>(),
    sources: createResource<OperationSources>(),
    a: side(),
    b: side(),
    autoMatch: true,
    operation: "add",
    match: createResource<null>(),
    inputs: createResource<OperationInputs>(),
    compute: createResource<OperationComputation>(),
    result: null,
    exporting: createResource<OperationExported>(),
    started: false,
  }) as CalcPageState;
  let matchGeneration = 0;

  /** The shown A/B charts belong to the current selection (the run button needs that). */
  function inputsCurrent(): boolean {
    const shown = state.inputs.data;
    return (
      shown !== null &&
      !state.inputs.loading &&
      state.inputs.error === null &&
      sameRef(shown.a, refOf(state.a)) &&
      sameRef(shown.b, refOf(state.b))
    );
  }

  function canRun(): boolean {
    return inputsCurrent() && state.inputs.data?.valid === true && !state.compute.loading;
  }

  /** Load `key`'s records into `entry`; the source changes only once its list has arrived (a failure keeps the
   * old source with its old list, V1.0.3 "先读完再改下拉框"). `keep` keeps that record selected when listed.
   * `retry` redoes the whole step that needed the list (choose a source, refresh), not just the list: a retried
   * list alone would leave the charts, time difference and result of the old source (review #51 M-1). */
  async function loadRecords(
    entry: Side,
    key: string,
    keep: number | null,
    retry: () => Promise<boolean>,
  ): Promise<boolean> {
    const ok = await run(entry.records, () => api.operationSpectra(key, keep));
    entry.records.retry = retry;
    if (!ok || entry.records.data === null) return false;
    entry.source = key;
    entry.blank = false;
    const items = entry.records.data.items;
    entry.selected = keep !== null && items.some((item) => item.id === keep) ? keep : (items[0]?.id ?? null);
    entry.extra = null;
    return true;
  }

  /** The selection changed: the result on screen and any calculation still pending go at once (UI-158, UI-266),
   * not only once the new charts have arrived, so nothing of the old inputs can be exported meanwhile (review
   * #51 M-3). */
  function dropResult(): void {
    state.result = null;
    invalidate(state.compute);
    state.compute.error = null;
  }

  /** Show the A/B charts of the current selection; any result goes (UI-158, UI-266). */
  async function showInputs(): Promise<boolean> {
    dropResult();
    const a = refOf(state.a);
    const b = refOf(state.b);
    const ok = await run(state.inputs, () => api.operationInputs(a, b));
    if (!ok && state.inputs.error?.code === "snapshot_changed") void refresh();
    return ok;
  }

  /** V1.0.3 _operation_a_changed: with the option on, pick B's record nearest in time to A; then redraw. */
  async function aChanged(): Promise<boolean> {
    const generation = ++matchGeneration;
    dropResult();
    const a = selectedCandidate(state.a);
    if (state.autoMatch && a !== null && state.b.source !== null) {
      const key = state.b.source;
      const ok = await run(state.match, async () => {
        const found = await api.operationNearest(key, a.acquired_at);
        if (generation !== matchGeneration || state.b.source !== key) return null;
        if (found.match === null) {
          state.b.selected = null;
          state.b.extra = null;
          state.b.blank = true;
        } else {
          const { time_difference_seconds: _difference, ...candidate } = found.match;
          state.b.blank = false;
          state.b.selected = candidate.id;
          state.b.extra = state.b.records.data?.items.some((item) => item.id === candidate.id) ? null : candidate;
        }
        return null;
      });
      state.match.retry = aChanged;
      if (generation !== matchGeneration) return false;
      if (!ok) return showInputs().then(() => false);
    }
    return showInputs();
  }

  let showing: Promise<boolean> | null = null;

  /** The page opened or the device list changed; calls made while one is running share it (no double start). */
  function show(): Promise<boolean> {
    showing ??= load().finally(() => {
      showing = null;
    });
    return showing;
  }

  /** First visit: texts, sources, A first and B second, then the nearest match (UI-156, UI-201). Later visits and
   * new imports refresh the lists and keep the selection (UI-204, UI-267). */
  async function load(): Promise<boolean> {
    if (state.page.data === null) {
      await run(state.page, () => api.operationPage());
      const loaded = state.page.data as OperationPage | null;
      if (loaded !== null && !state.started) state.operation = loaded.default_operation;
    }
    return state.started ? refresh() : start();
  }

  async function start(): Promise<boolean> {
    const ok = await run(state.sources, () => api.operationSources());
    state.sources.retry = show;
    const found = state.sources.data;
    if (!ok || found === null) return false;
    state.started = true;
    for (const [entry, key] of [
      [state.a, found.initial_a],
      [state.b, found.initial_b],
    ] as const) {
      if (key === null) continue;
      const first = (): Promise<boolean> => loadRecords(entry, key, null, first).then((ok) => ok && aChanged());
      await loadRecords(entry, key, null, first);
    }
    return aChanged();
  }

  /** The source a side shows after the source list changed: its own if still there, else V1.0.3's default. */
  function sourceAfter(entry: Side, fallback: number): string | null {
    const keys = state.sources.data?.items.map((item) => item.key) ?? [];
    if (entry.source !== null && keys.includes(entry.source)) return entry.source;
    return keys[Math.min(fallback, keys.length - 1)] ?? null;
  }

  async function refresh(): Promise<boolean> {
    const ok = await run(state.sources, () => api.operationSources());
    state.sources.retry = refresh;
    if (!ok) return false;
    let changed = false;
    for (const [entry, fallback] of [
      [state.a, 0],
      [state.b, 1],
    ] as const) {
      const before = { source: entry.source, id: entry.selected, snapshot: entry.records.data?.snapshot_id ?? null };
      const key = sourceAfter(entry, fallback);
      if (key === null) {
        entry.source = null;
        entry.selected = null;
        entry.extra = null;
        reset(entry.records);
      } else {
        await loadRecords(entry, key, key === before.source ? before.id : null, refresh); // an older kept record is listed last
      }
      const after = { source: entry.source, id: entry.selected, snapshot: entry.records.data?.snapshot_id ?? null };
      changed ||= before.source !== after.source || before.id !== after.id || before.snapshot !== after.snapshot;
    }
    if (changed || state.inputs.data === null) return showInputs();
    return true;
  }

  async function setSource(which: SideKey, key: string): Promise<boolean> {
    const entry = state[which];
    const retry = () => setSource(which, key);
    if (!(await loadRecords(entry, key, entry.source === key ? entry.selected : null, retry))) return false;
    return aChanged(); // V1.0.3 _operation_database_changed: both sides end in _operation_a_changed
  }

  async function setRecord(which: SideKey, id: number): Promise<boolean> {
    state[which].selected = id;
    if (which === "a") return aChanged();
    ++matchGeneration; // UI-205: a match still pending for an earlier A must not replace the hand-picked B (M-2)
    reset(state.match); // nor may its error's retry, which would rematch B
    return showInputs(); // UI-205: a hand-picked B changes nothing on A
  }

  async function setAutoMatch(on: boolean): Promise<boolean> {
    state.autoMatch = on;
    return aChanged(); // UI-203: switching it back on matches at once; either way the result goes
  }

  function setOperation(operation: OperationKey): void {
    state.operation = operation;
    state.result = null; // UI-158
    invalidate(state.compute);
    state.compute.error = null;
  }

  /** UI-186, UI-187: exchange sources and records exactly, no matching; the result goes. */
  async function swap(): Promise<boolean> {
    if (!canRun()) return false;
    ++matchGeneration;
    const a = { ...state.a };
    Object.assign(state.a, { source: state.b.source, records: state.b.records, selected: state.b.selected });
    Object.assign(state.a, { extra: state.b.extra, blank: state.b.blank });
    Object.assign(state.b, { source: a.source, records: a.records, selected: a.selected, extra: a.extra, blank: a.blank });
    for (const entry of [state.a, state.b]) {
      entry.records.error = null; // a failed source change belonged to the other side: drop it with its retry
      entry.records.retry = null;
    }
    return showInputs();
  }

  async function calculate(): Promise<boolean> {
    const a = refOf(state.a);
    const b = refOf(state.b);
    if (!canRun() || a === null || b === null) return false;
    const operation = state.operation;
    const ok = await run(state.compute, () => api.operationCompute(a, b, operation));
    if (ok && state.compute.data !== null) {
      state.result = state.compute.data;
      state.inputs.data = state.compute.data;
    } else if (state.compute.error?.code === "snapshot_changed") {
      void refresh();
    }
    return ok;
  }

  /** EXP-022: the result on screen is exported, whatever is selected now. Cancelling never gets here (EXP-021). */
  async function exportResult(formats: ExportKind[]): Promise<boolean> {
    const shown = state.result;
    if (shown === null || formats.length === 0) return false;
    const a: SourceRef = { source: shown.a.source ?? "", id: shown.a.id ?? 0, snapshot_id: shown.a.snapshot_id };
    const b: SourceRef = { source: shown.b.source ?? "", id: shown.b.id ?? 0, snapshot_id: shown.b.snapshot_id };
    return run(state.exporting, () => api.operationExport(a, b, shown.result.operation, formats));
  }

  function clearExport(): void {
    reset(state.exporting);
  }

  return {
    state,
    show,
    refresh,
    setSource,
    setRecord,
    setAutoMatch,
    setOperation,
    swap,
    calculate,
    exportResult,
    clearExport,
    canRun,
    inputsCurrent,
  };
}
