/**
 * A value loaded from the service that keeps its last valid data when a later load fails (R-1-5, UI-316).
 *
 * `run` replaces `data` only on success; on failure `data` stays and `error` says why, so the page can show the
 * reason and offer a retry. `clearOn` names error codes after which the old data must go (UI-032: a record that
 * no longer exists empties the detail). Answers to superseded calls are dropped, so a slow old answer can never
 * overwrite a newer one.
 */
import { reactive } from "vue";
import { ApiError } from "../api/client";

export interface Resource<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  /** the last call, for "重试" */
  retry: (() => Promise<boolean>) | null;
}

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(0, { code: "internal", message: "页面内部错误，请重试", retryable: true, detail: String(error) });
}

export function createResource<T>(): Resource<T> {
  return reactive({ data: null, error: null, loading: false, retry: null }) as Resource<T>;
}

const generations = new WeakMap<object, number>();

/** Load into `resource`; resolves true when this call's data is now shown. */
export async function run<T>(
  resource: Resource<T>,
  load: () => Promise<T>,
  clearOn: readonly string[] = [],
): Promise<boolean> {
  const generation = (generations.get(resource) ?? 0) + 1;
  generations.set(resource, generation);
  resource.loading = true;
  resource.retry = () => run(resource, load, clearOn);
  try {
    const data = await load();
    if (generations.get(resource) !== generation) return false;
    resource.data = data;
    resource.error = null;
    return true;
  } catch (error) {
    if (generations.get(resource) !== generation) return false;
    const failure = asApiError(error);
    resource.error = failure;
    if (clearOn.includes(failure.code)) resource.data = null;
    return false;
  } finally {
    if (generations.get(resource) === generation) resource.loading = false;
  }
}

/**
 * Keep the shown data but drop every pending answer (review M-1): when what must be shown is already in
 * `data` (a cache hit), a slower load started earlier must not overwrite it when it finally answers. The retry
 * of that cancelled load goes too (review question on PR #46): with `error` still null the button never shows
 * today, but a kept handle would re-run the cancelled load (e.g. another record) and replace the shown data.
 */
export function invalidate<T>(resource: Resource<T>): void {
  generations.set(resource, (generations.get(resource) ?? 0) + 1);
  resource.loading = false;
  resource.retry = null;
}

/** Forget the data and error (e.g. when the query yields no record, UI-032). Pending answers are dropped. */
export function reset<T>(resource: Resource<T>): void {
  generations.set(resource, (generations.get(resource) ?? 0) + 1);
  resource.data = null;
  resource.error = null;
  resource.loading = false;
  resource.retry = null;
}
