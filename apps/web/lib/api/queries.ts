"use client";

import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { segment, useApi } from "@/lib/api/client";
import type {
  AgeBasisMode,
  AuditTrail,
  CaseDetail,
  CaseList,
  CaseStatus,
  DemographyException,
  DemographyPage,
  ExceptionQueue,
  ManualInputs,
  ManualInputsResult,
  QuoteGrid,
  RecalculateResult,
  SublimitOption,
  SublimitRow,
} from "@/lib/api/types";

export const queryKeys = {
  cases: (params: object) => ["cases", params] as const,
  case: (id: string) => ["case", id] as const,
  extractions: (id: string) => ["case", id, "extractions"] as const,
  sublimits: (id: string) => ["case", id, "sublimits"] as const,
  demography: (id: string, flaggedOnly: boolean) =>
    ["case", id, "demography", { flaggedOnly }] as const,
  exceptions: (id: string, params: object) =>
    ["case", id, "exceptions", params] as const,
  audit: (id: string) => ["case", id, "audit"] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export function useCases(params: {
  status: CaseStatus[];
  q: string;
  page: number;
  pageSize: number;
}) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.cases(params),
    queryFn: () =>
      api.json<CaseList>("/cases", {
        params: {
          status: params.status,
          q: params.q,
          page: params.page,
          page_size: params.pageSize,
        },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useCase(caseId: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.case(caseId),
    queryFn: () => api.json<CaseDetail>(`/cases/${caseId}`),
  });
}

export function useExtractions(caseId: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.extractions(caseId),
    queryFn: () => api.json<QuoteGrid>(`/cases/${caseId}/extractions`),
  });
}

export function useSublimits(caseId: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.sublimits(caseId),
    queryFn: () =>
      api.json<{ rows: SublimitRow[] }>(`/cases/${caseId}/sublimits`),
    select: (data) => data.rows,
  });
}

export const DEMOGRAPHY_PAGE_SIZE = 1000;

/** Roster pages for the virtualized grid; the next page loads as the user scrolls. */
export function useDemography(caseId: string, flaggedOnly: boolean) {
  const api = useApi();
  return useInfiniteQuery({
    queryKey: queryKeys.demography(caseId, flaggedOnly),
    queryFn: ({ pageParam }) =>
      api.json<DemographyPage>(`/cases/${caseId}/demography`, {
        params: {
          page: pageParam,
          page_size: DEMOGRAPHY_PAGE_SIZE,
          flagged_only: flaggedOnly,
        },
      }),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
}

export function useExceptions(
  caseId: string,
  params: { resolved: boolean | null },
) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.exceptions(caseId, params),
    queryFn: () =>
      api.json<ExceptionQueue>(`/cases/${caseId}/demography/exceptions`, {
        params: { resolved: params.resolved, page_size: 500 },
      }),
  });
}

export function useAuditTrail(caseId: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.audit(caseId),
    queryFn: () =>
      api.json<AuditTrail>(`/cases/${caseId}/audit`, {
        params: { page_size: 500 },
      }),
  });
}

// ---------------------------------------------------------------------------
// Writes (each one also writes an audit_logs row server-side)
// ---------------------------------------------------------------------------

/** Refreshes everything that hangs off a case after an override. */
function useInvalidateCase(caseId: string) {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: queryKeys.case(caseId) });
}

export function useUpdateManualInputs(caseId: string) {
  const api = useApi();
  const invalidate = useInvalidateCase(caseId);
  return useMutation({
    mutationFn: (body: Partial<ManualInputs>) =>
      api.json<ManualInputsResult>(`/cases/${caseId}/manual-inputs`, {
        method: "PATCH",
        body,
      }),
    onSuccess: invalidate,
  });
}

export function useOverrideField(caseId: string) {
  const api = useApi();
  const invalidate = useInvalidateCase(caseId);
  return useMutation({
    mutationFn: ({
      fieldName,
      ...body
    }: {
      fieldName: string;
      coverage_details?: string | null;
      proposed_details?: string | null;
      justification: string;
    }) =>
      api.json(`/cases/${caseId}/extractions/${segment(fieldName)}`, {
        method: "PATCH",
        body,
      }),
    onSuccess: invalidate,
  });
}

export function useApproveSublimit(caseId: string) {
  const api = useApi();
  const invalidate = useInvalidateCase(caseId);
  return useMutation({
    mutationFn: ({
      procedureName,
      ...body
    }: {
      procedureName: string;
      matched_option: SublimitOption;
      justification: string;
    }) =>
      api.json(`/cases/${caseId}/sublimits/${segment(procedureName)}`, {
        method: "PATCH",
        body,
      }),
    onSuccess: invalidate,
  });
}

export function useRecalculateAge(caseId: string) {
  const api = useApi();
  const invalidate = useInvalidateCase(caseId);
  return useMutation({
    mutationFn: (body: {
      basis_mode: AgeBasisMode;
      proposal_start_date?: string | null;
    }) =>
      api.json<RecalculateResult>(
        `/cases/${caseId}/demography/recalculate-age`,
        { method: "POST", body },
      ),
    onSuccess: invalidate,
  });
}

export function useResolveException(caseId: string) {
  const api = useApi();
  const invalidate = useInvalidateCase(caseId);
  return useMutation({
    mutationFn: ({
      exceptionId,
      ...body
    }: {
      exceptionId: string;
      resolution_action: string;
      is_resolved?: boolean;
    }) =>
      api.json<DemographyException>(
        `/cases/${caseId}/demography/exceptions/${exceptionId}`,
        { method: "PATCH", body },
      ),
    onSuccess: invalidate,
  });
}
