/**
 * The reference curves and fill colours of the spectrum charts (API-08), loaded once for every page.
 *
 * App provides the store under REFERENCE_CURVES and calls load() when it mounts and on each page change; a chart
 * injects it and draws the V1.0.3 coloured fill and curves once the data is there, the plain line until then. The
 * content is fixed, so a loaded store never asks again; a failed load keeps nothing and the next load() tries again
 * (R-1-5: the chart stays usable meanwhile).
 */
import type { InjectionKey } from "vue";
import type { ApiClient } from "../api/client";
import type { ReferenceCurves } from "../api/types";
import { createResource, run, type Resource } from "../lib/resource";

export interface ReferenceStore {
  state: Resource<ReferenceCurves>;
  load(): Promise<void>;
}

export const REFERENCE_CURVES: InjectionKey<ReferenceStore> = Symbol("reference-curves");

export function createReferenceStore(api: ApiClient): ReferenceStore {
  const state = createResource<ReferenceCurves>();
  return {
    state,
    async load() {
      if (state.data !== null || state.loading) return;
      await run(state, () => api.referenceCurves());
    },
  };
}
