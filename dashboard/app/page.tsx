"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type PendingRequest = {
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

const fallbackApiBase = (() => {
  if (typeof window === "undefined") return "http://127.0.0.1:8788";
  const { protocol, hostname } = window.location;
  const host = hostname || "127.0.0.1";
  return `${protocol}//${host}:8788`;
})();

const defaultBaseUrl =
  process.env.NEXT_PUBLIC_CTRL_API_BASE || fallbackApiBase;

const defaultDbPath =
  process.env.NEXT_PUBLIC_CTRL_DB_PATH ?? "/data/ctrl.db";
const defaultServersPath =
  process.env.NEXT_PUBLIC_CTRL_SERVERS_PATH ?? "configs/servers.yaml";

const parseResponse = async <T,>(response: Response): Promise<T> => {
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail ?? text;
    } catch {
      // Leave detail as text when JSON parsing fails.
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

export default function ConsolePage() {
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
  const [dbPath, setDbPath] = useState(defaultDbPath);
  const [serversPath, setServersPath] = useState(defaultServersPath);
  const [approvedBy, setApprovedBy] = useState("human");
  const [pending, setPending] = useState<PendingRequest[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusId, setStatusId] = useState("");
  const [statusData, setStatusData] = useState<StatusResponse | null>(null);
  const [loadingPending, setLoadingPending] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
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

  const loadPending = useCallback(async () => {
    setLoadingPending(true);
    setNotice(null);
    try {
      const url = makeUrl("pending", baseParams);
      const data = await parseResponse<PendingRequest[]>(await fetch(url));
      setPending(data);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to load pending queue.";
      setNotice({ type: "error", message });
    } finally {
      setLoadingPending(false);
    }
  }, [baseParams, makeUrl]);

  const loadStatus = useCallback(
    async (requestId: string) => {
      const trimmed = requestId.trim();
      if (!trimmed) {
        setNotice({
          type: "error",
          message: "Request ID is required to fetch status.",
        });
        return;
      }
      setLoadingStatus(true);
      setNotice(null);
      try {
        const url = makeUrl(`status/${trimmed}`, baseParams);
        const data = await parseResponse<StatusResponse>(await fetch(url));
        setStatusData(data);
        setSelectedId(trimmed);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to load status.";
        setNotice({ type: "error", message });
      } finally {
        setLoadingStatus(false);
      }
    },
    [baseParams, makeUrl]
  );

  const runAction = useCallback(
    async (requestId: string, action: "approve" | "deny") => {
      const trimmed = requestId.trim();
      if (!trimmed) {
        return;
      }
      setActionId(trimmed);
      setNotice(null);
      try {
        const params = {
          ...baseParams,
          servers_path:
            action === "approve" ? serversPath.trim() || undefined : undefined,
        };
        const url = makeUrl(`${action}/${trimmed}`, params);
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            approved_by: approvedBy.trim() || "human",
          }),
        });
        const result = await parseResponse<{ ok: boolean; status: string }>(
          response
        );
        setNotice({
          type: "success",
          message: `Request ${trimmed} ${result.status}.`,
        });
        await loadPending();
        if (selectedId === trimmed || statusId.trim() === trimmed) {
          await loadStatus(trimmed);
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Action failed.";
        setNotice({ type: "error", message });
      } finally {
        setActionId(null);
      }
    },
    [
      approvedBy,
      baseParams,
      loadPending,
      loadStatus,
      makeUrl,
      selectedId,
      serversPath,
      statusId,
    ]
  );

  useEffect(() => {
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;
    loadPending();
  }, [loadPending]);

  const pendingCount = pending.length;

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
                Approvals console
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-3 rounded-full border border-[var(--stroke)] bg-white/70 px-4 py-2 text-sm font-semibold text-[var(--ink)] shadow-sm">
                <span className="inline-flex h-2 w-2 rounded-full bg-[var(--accent-2)]" />
                {pendingCount} pending
              </div>
              <Link
                className="btn rounded-full border border-[var(--stroke)] bg-white/90 px-4 py-2 text-sm font-semibold text-[var(--ink)]"
                href="/requests"
              >
                View all requests
              </Link>
            </div>
          </div>
          <p className="max-w-2xl text-lg text-[var(--muted)]">
            Monitor MCP tool requests, inspect arguments, and approve or deny
            with a single audit-friendly workflow.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="flex flex-col gap-6 animate-fade-up delay-1">
            <div className="panel rounded-3xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-[var(--ink)]">
                    Connection defaults
                  </h2>
                  <p className="text-sm text-[var(--muted)]">
                    Configure where the dashboard sends requests.
                  </p>
                </div>
                <button
                  className="btn rounded-full bg-[var(--accent-3)] px-4 py-2 text-sm font-semibold text-white shadow-sm"
                  onClick={loadPending}
                  disabled={loadingPending}
                >
                  {loadingPending ? "Refreshing..." : "Refresh queue"}
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
                      Servers config path
                    </label>
                    <input
                      className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                      value={serversPath}
                      onChange={(event) => setServersPath(event.target.value)}
                      placeholder="configs/servers.yaml"
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-[1.2fr_auto]">
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                      Approved by
                    </label>
                    <input
                      className="w-full rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                      value={approvedBy}
                      onChange={(event) => setApprovedBy(event.target.value)}
                      placeholder="human"
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      className="btn w-full rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm font-semibold text-[var(--ink)]"
                      onClick={() => {
                        setBaseUrl(defaultBaseUrl);
                        setDbPath(defaultDbPath);
                        setServersPath(defaultServersPath);
                        setApprovedBy("human");
                      }}
                    >
                      Reset defaults
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel rounded-3xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-[var(--ink)]">
                    Pending requests
                  </h2>
                  <p className="text-sm text-[var(--muted)]">
                    Select a request to inspect or take action.
                  </p>
                </div>
                <div className="rounded-full border border-[var(--stroke)] bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
                  {pendingCount} queued
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-4">
                {pending.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[var(--stroke)] bg-white/60 p-6 text-sm text-[var(--muted)]">
                    {loadingPending
                      ? "Loading pending requests..."
                      : "No pending requests right now."}
                  </div>
                ) : (
                  pending.map((item) => {
                    const isSelected = selectedId === item.id;
                    return (
                      <div
                        key={item.id}
                        className={`rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 transition hover:-translate-y-0.5 ${
                          isSelected ? "ring-2 ring-[var(--accent-3)]" : ""
                        }`}
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
                          <div className="flex items-center gap-2">
                            <span className={`chip ${statusTone(item.status)}`}>
                              {item.status}
                            </span>
                            <span
                              className={`chip ${riskTone(item.risk_score)}`}
                            >
                              risk {formatRisk(item.risk_score)}
                            </span>
                          </div>
                        </div>

                        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--muted)]">
                          <div className="flex flex-wrap items-center gap-4">
                            <span>env: {item.env || "-"}</span>
                            <span>created: {formatDate(item.created_at)}</span>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              className="btn rounded-full border border-[var(--stroke)] bg-white/95 px-3 py-1 text-xs font-semibold text-[var(--ink)]"
                              onClick={() => {
                                setStatusId(item.id);
                                loadStatus(item.id);
                              }}
                            >
                              View
                            </button>
                            {item.status === "pending" && (
                              <>
                                <button
                                  className="btn rounded-full bg-[var(--accent-2)] px-3 py-1 text-xs font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                                  onClick={() => runAction(item.id, "approve")}
                                  disabled={actionId === item.id}
                                >
                                  {actionId === item.id
                                    ? "Working"
                                    : "Approve"}
                                </button>
                                <button
                                  className="btn rounded-full bg-[var(--accent)] px-3 py-1 text-xs font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                                  onClick={() => runAction(item.id, "deny")}
                                  disabled={actionId === item.id}
                                >
                                  {actionId === item.id ? "Working" : "Deny"}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </section>

          <section className="flex flex-col gap-6 animate-fade-up delay-2">
            <div className="panel rounded-3xl p-6">
              <h2 className="text-xl font-semibold text-[var(--ink)]">
                Status lookup
              </h2>
              <p className="text-sm text-[var(--muted)]">
                Fetch any request by ID, even if it is not pending.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <input
                  className="w-full flex-1 rounded-2xl border border-[var(--stroke)] bg-white/80 px-4 py-3 text-sm text-[var(--ink)] shadow-sm outline-none transition focus:border-[var(--accent-3)] focus:ring-2 focus:ring-[var(--accent-3)]"
                  value={statusId}
                  onChange={(event) => setStatusId(event.target.value)}
                  placeholder="Request ID"
                />
                <button
                  className="btn rounded-full bg-[var(--accent-3)] px-5 py-3 text-sm font-semibold text-white shadow-sm"
                  onClick={() => loadStatus(statusId)}
                  disabled={loadingStatus}
                >
                  {loadingStatus ? "Loading..." : "Get status"}
                </button>
              </div>
            </div>

            <div className="panel rounded-3xl p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-[var(--ink)]">
                    Request detail
                  </h2>
                  <p className="text-sm text-[var(--muted)]">
                    Full payload and most recent decision.
                  </p>
                </div>
                {statusData?.request?.status && (
                  <span
                    className={`chip px-4 py-2 ${statusTone(
                      statusData.request.status
                    )}`}
                  >
                    {statusData.request.status}
                  </span>
                )}
              </div>

              {!statusData ? (
                <div className="mt-6 rounded-2xl border border-dashed border-[var(--stroke)] bg-white/60 p-6 text-sm text-[var(--muted)]">
                  {loadingStatus
                    ? "Loading status..."
                    : "Select a pending request or fetch by ID to see details."}
                </div>
              ) : (
                <div className="mt-6 flex flex-col gap-6">
                  <div className="rounded-2xl border border-[var(--stroke)] bg-white/85 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="mono text-xs text-[var(--muted)]">
                          {statusData.request.id}
                        </p>
                        <p className="text-lg font-semibold text-[var(--ink)]">
                          {statusData.request.server} / {statusData.request.tool}
                        </p>
                      </div>
                      <span
                        className={`chip ${riskTone(
                          statusData.request.risk_score
                        )}`}
                      >
                        risk {formatRisk(statusData.request.risk_score)}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-4 text-sm text-[var(--muted)]">
                      <span>env: {statusData.request.env || "-"}</span>
                      <span>
                        created: {formatDate(statusData.request.created_at)}
                      </span>
                    </div>

                    {statusData.request.status === "pending" && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button
                          className="btn rounded-full bg-[var(--accent-2)] px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                          onClick={() =>
                            runAction(statusData.request.id, "approve")
                          }
                          disabled={actionId === statusData.request.id}
                        >
                          {actionId === statusData.request.id
                            ? "Working"
                            : "Approve"}
                        </button>
                        <button
                          className="btn rounded-full bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                          onClick={() =>
                            runAction(statusData.request.id, "deny")
                          }
                          disabled={actionId === statusData.request.id}
                        >
                          {actionId === statusData.request.id
                            ? "Working"
                            : "Deny"}
                        </button>
                      </div>
                    )}
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                      Arguments
                    </h3>
                    <pre className="mono mt-3 max-h-64 overflow-auto rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 text-xs text-[var(--ink)]">
                      {JSON.stringify(
                        statusData.request.arguments ?? {},
                        null,
                        2
                      )}
                    </pre>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                      Tool result
                    </h3>
                    {statusData.request.result_preview ? (
                      <pre className="mono mt-3 max-h-64 overflow-auto rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 text-xs text-[var(--ink)]">
                        {statusData.request.result_preview}
                      </pre>
                    ) : (
                      <div className="mt-3 rounded-2xl border border-dashed border-[var(--stroke)] bg-white/60 p-4 text-sm text-[var(--muted)]">
                        No result recorded yet.
                      </div>
                    )}
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                      Decision
                    </h3>
                    {statusData.decision ? (
                      <div className="mt-3 rounded-2xl border border-[var(--stroke)] bg-white/80 p-4 text-sm text-[var(--ink)]">
                        <div className="flex flex-wrap gap-4">
                          <span className="font-semibold">
                            {statusData.decision.decision}
                          </span>
                          <span className="text-[var(--muted)]">
                            {formatDate(statusData.decision.decided_at)}
                          </span>
                        </div>
                        <p className="mt-2 text-[var(--muted)]">
                          Policy: {statusData.decision.policy_id || "-"}
                        </p>
                        <p className="mt-1 text-[var(--muted)]">
                          Reason: {statusData.decision.reason || "-"}
                        </p>
                      </div>
                    ) : (
                      <div className="mt-3 rounded-2xl border border-dashed border-[var(--stroke)] bg-white/60 p-4 text-sm text-[var(--muted)]">
                        No decision recorded yet.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

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
          </section>
        </div>
      </div>
    </div>
  );
}
