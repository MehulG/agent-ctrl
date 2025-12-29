"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type RequestItem = {
  id: string;
  created_at: string;
  server: string;
  tool: string;
  env: string;
  status: string;
  risk_score: number | null;
};

type StatusRequest = {
  id: string;
  created_at: string;
  server: string;
  tool: string;
  env: string;
  status: string;
  risk_score: number | null;
  arguments: Record<string, unknown>;
  result_preview?: string | null;
};

type StatusDecision = {
  decided_at: string;
  decision: string;
  policy_id: string | null;
  reason: string | null;
};

type StatusResponse = {
  request: StatusRequest;
  decision: StatusDecision | null;
};

type Notice = {
  type: "error" | "success" | "info";
  message: string;
};

const defaultBaseUrl =
  process.env.NEXT_PUBLIC_CTRL_API_BASE ?? "http://127.0.0.1:8788";
const defaultDbPath = "ctrl.db";

const parseResponse = async <T,>(response: Response): Promise<T> => {
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail ?? text;
    } catch {
      // Ignore JSON parse errors.
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }

  if (!text) {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
};

const formatDate = (value: string) => {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

const formatRisk = (score: number | null | undefined) => {
  if (typeof score !== "number") {
    return "n/a";
  }
  return `${score}`;
};

const riskTone = (score: number | null | undefined) => {
  if (typeof score !== "number") {
    return "bg-white/80 text-[var(--muted)] border-[var(--stroke)]";
  }
  if (score >= 80) {
    return "bg-[var(--accent)] text-white";
  }
  if (score >= 40) {
    return "bg-[#ffe1b8] text-[#6e3f00] border-[#f3c68a]";
  }
  return "bg-[var(--accent-2)] text-white";
};

const statusTone = (status?: string) => {
  const normalized = status?.toLowerCase();
  if (normalized === "pending") {
    return "bg-[var(--accent-3)] text-white";
  }
  if (normalized === "approved" || normalized === "executed") {
    return "bg-[var(--accent-2)] text-white";
  }
  if (normalized === "denied") {
    return "bg-[var(--accent)] text-white";
  }
  if (normalized === "failed") {
    return "bg-black/80 text-white";
  }
  return "bg-white/80 text-[var(--muted)] border-[var(--stroke)]";
};

const statusOptions = [
  "all",
  "pending",
  "approved",
  "executed",
  "denied",
  "failed",
];

export default function RequestsPage() {
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
  const [dbPath, setDbPath] = useState(defaultDbPath);
  const [statusFilter, setStatusFilter] = useState("all");
  const [limit, setLimit] = useState("200");
  const [items, setItems] = useState<RequestItem[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailsById, setDetailsById] = useState<
    Record<string, StatusResponse>
  >({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const hasLoadedRef = useRef(false);

  const baseParams = useMemo(
    () => ({
      db_path: dbPath.trim() || undefined,
    }),
    [dbPath]
  );

  const makeUrl = useCallback(
    (path: string, params: Record<string, string | undefined>) => {
      const trimmed = baseUrl.trim();
      if (!trimmed) {
        throw new Error("Base URL is required.");
      }
      const normalized = trimmed.endsWith("/") ? trimmed : `${trimmed}/`;
      const url = new URL(path.replace(/^\/+/, ""), normalized);
      Object.entries(params).forEach(([key, value]) => {
        if (value) {
          url.searchParams.set(key, value);
        }
      });
      return url.toString();
    },
    [baseUrl]
  );

  const loadRequests = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const params: Record<string, string | undefined> = {
        ...baseParams,
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: limit.trim() || undefined,
      };
      const url = makeUrl("requests", params);
      const data = await parseResponse<RequestItem[]>(await fetch(url));
      setItems(data);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to load requests.";
      setNotice({ type: "error", message });
    } finally {
      setLoading(false);
    }
  }, [baseParams, limit, makeUrl, statusFilter]);

  const loadDetails = useCallback(
    async (requestId: string) => {
      if (detailsById[requestId]) {
        return;
      }
      setLoadingId(requestId);
      setNotice(null);
      try {
        const url = makeUrl(`status/${requestId}`, baseParams);
        const data = await parseResponse<StatusResponse>(await fetch(url));
        setDetailsById((prev) => ({ ...prev, [requestId]: data }));
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to load request.";
        setNotice({ type: "error", message });
      } finally {
        setLoadingId((current) => (current === requestId ? null : current));
      }
    },
    [baseParams, detailsById, makeUrl]
  );

  useEffect(() => {
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;
    loadRequests();
  }, [loadRequests]);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="page-bg absolute inset-0" />
      <div className="page-pattern absolute inset-0" />

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col gap-10 px-6 py-12 lg:px-10">
        <header className="flex flex-col gap-6 animate-fade-up">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="mono text-xs uppercase tracking-[0.4em] text-[var(--muted)]">
                ctrl approvals
              </p>
              <h1 className="text-4xl font-semibold tracking-tight text-[var(--ink)] sm:text-5xl">
                Request ledger
              </h1>
            </div>
            <Link
              className="btn rounded-full border border-[var(--stroke)] bg-white/90 px-4 py-2 text-sm font-semibold text-[var(--ink)]"
              href="/"
            >
              Back to approvals
            </Link>
          </div>
          <p className="max-w-2xl text-lg text-[var(--muted)]">
            Full request history from the ctrl ledger. Filter by status or scan
            across servers, tools, and risk scores.
          </p>
        </header>

        <section className="panel rounded-3xl p-6 animate-fade-up delay-1">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-[var(--ink)]">
                Query settings
              </h2>
              <p className="text-sm text-[var(--muted)]">
                Adjust filters before refreshing the ledger.
              </p>
            </div>
            <button
              className="btn rounded-full bg-[var(--accent-3)] px-4 py-2 text-sm font-semibold text-white shadow-sm"
              onClick={loadRequests}
              disabled={loading}
            >
              {loading ? "Refreshing..." : "Refresh list"}
            </button>
          </div>

          <div className="mt-6 grid gap-4">
            <label className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
              API base URL
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="http://127.0.0.1:8788"
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                  Database path
                </label>
                <input
                  className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                  value={dbPath}
                  onChange={(event) => setDbPath(event.target.value)}
                  placeholder="ctrl.db"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                  Status filter
                </label>
                <select
                  className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                >
                  {statusOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-[1.1fr_auto]">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                  Limit
                </label>
                <input
                  className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                  value={limit}
                  onChange={(event) => setLimit(event.target.value)}
                  placeholder="200"
                />
              </div>
              <div className="flex items-end">
                <button
                  className="btn w-full rounded-full border border-[var(--stroke)] bg-white/90 px-4 py-3 text-sm font-semibold text-[var(--ink)]"
                  onClick={() => {
                    setBaseUrl(defaultBaseUrl);
                    setDbPath(defaultDbPath);
                    setStatusFilter("all");
                    setLimit("200");
                  }}
                >
                  Reset defaults
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="panel rounded-3xl p-6 animate-fade-up delay-2">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-[var(--ink)]">
                Requests
              </h2>
              <p className="text-sm text-[var(--muted)]">
                Showing {items.length} entries.
              </p>
            </div>
            <span className="chip bg-white/80 text-[var(--muted)] border-[var(--stroke)]">
              {statusFilter === "all" ? "all statuses" : statusFilter}
            </span>
          </div>

          <div className="mt-6 flex flex-col gap-4">
            {items.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--stroke)] bg-white/60 p-6 text-sm text-[var(--muted)]">
                {loading ? "Loading requests..." : "No requests found."}
              </div>
            ) : (
              items.map((item) => {
                const isExpanded = expandedId === item.id;
                const details = detailsById[item.id];
                return (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-[var(--stroke)] bg-white/80 p-4"
                  >
                    <div
                      className="cursor-pointer"
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        const next = isExpanded ? null : item.id;
                        setExpandedId(next);
                        if (!isExpanded) {
                          loadDetails(item.id);
                        }
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          const next = isExpanded ? null : item.id;
                          setExpandedId(next);
                          if (!isExpanded) {
                            loadDetails(item.id);
                          }
                        }
                      }}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="mono text-xs text-[var(--muted)]">
                            {item.id}
                          </p>
                          <p className="text-lg font-semibold text-[var(--ink)]">
                            {item.server} / {item.tool}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`chip ${statusTone(item.status)}`}>
                            {item.status}
                          </span>
                          <span className={`chip ${riskTone(item.risk_score)}`}>
                            risk {formatRisk(item.risk_score)}
                          </span>
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-[var(--muted)]">
                        <span>env: {item.env || "-"}</span>
                        <span>created: {formatDate(item.created_at)}</span>
                      </div>
                      <div className="mt-3 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
                        {isExpanded ? "Hide details" : "Show details"}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="mt-4 rounded-2xl border border-[var(--stroke)] bg-white/90 p-4">
                        {loadingId === item.id && !details ? (
                          <div className="text-sm text-[var(--muted)]">
                            Loading details...
                          </div>
                        ) : details ? (
                          <div className="grid gap-4">
                            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                              <div>
                                <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                                  Arguments
                                </h3>
                                <pre className="mono mt-2 max-h-52 overflow-auto rounded-2xl border border-[var(--stroke)] bg-white p-3 text-xs text-[var(--ink)]">
                                  {JSON.stringify(
                                    details.request.arguments ?? {},
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                              <div className="flex flex-col gap-3 text-sm text-[var(--muted)]">
                                <div>
                                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                                    Status
                                  </p>
                                  <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <span
                                      className={`chip ${statusTone(
                                        details.request.status
                                      )}`}
                                    >
                                      {details.request.status}
                                    </span>
                                    <span
                                      className={`chip ${riskTone(
                                        details.request.risk_score
                                      )}`}
                                    >
                                      risk{" "}
                                      {formatRisk(details.request.risk_score)}
                                    </span>
                                  </div>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                                    Decision
                                  </p>
                                  {details.decision ? (
                                    <div className="mt-2 rounded-2xl border border-[var(--stroke)] bg-white p-3 text-sm text-[var(--ink)]">
                                      <div className="flex flex-wrap gap-4">
                                        <span className="font-semibold">
                                          {details.decision.decision}
                                        </span>
                                        <span className="text-[var(--muted)]">
                                          {formatDate(
                                            details.decision.decided_at
                                          )}
                                        </span>
                                      </div>
                                      <p className="mt-2 text-[var(--muted)]">
                                        Policy:{" "}
                                        {details.decision.policy_id || "-"}
                                      </p>
                                      <p className="mt-1 text-[var(--muted)]">
                                        Reason: {details.decision.reason || "-"}
                                      </p>
                                    </div>
                                  ) : (
                                    <div className="mt-2 rounded-2xl border border-dashed border-[var(--stroke)] bg-white p-3 text-sm text-[var(--muted)]">
                                      No decision recorded yet.
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div>
                              <h3 className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                                Tool result
                              </h3>
                              {details.request.result_preview ? (
                                <pre className="mono mt-2 max-h-52 overflow-auto rounded-2xl border border-[var(--stroke)] bg-white p-3 text-xs text-[var(--ink)]">
                                  {details.request.result_preview}
                                </pre>
                              ) : (
                                <div className="mt-2 rounded-2xl border border-dashed border-[var(--stroke)] bg-white p-3 text-sm text-[var(--muted)]">
                                  No result recorded yet.
                                </div>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="text-sm text-[var(--muted)]">
                            Details unavailable.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>

        {notice && (
          <div
            className={`panel-strong rounded-3xl border border-[var(--stroke)] px-5 py-4 text-sm font-semibold ${
              notice.type === "error"
                ? "text-[var(--accent)]"
                : notice.type === "success"
                  ? "text-[var(--accent-2)]"
                  : "text-[var(--muted)]"
            }`}
          >
            {notice.message}
          </div>
        )}
      </div>
    </div>
  );
}
