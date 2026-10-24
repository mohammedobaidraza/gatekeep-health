"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, scoreLevel, statusLevel } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Caption } from "@/components/ui/Panel";
import { PageHeader, Shell } from "@/components/ui/Shell";
import { Stat } from "@/components/ui/Stat";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { Tabs } from "@/components/ui/Tabs";
import { EmployeeSummary, getEmployees } from "@/lib/api";

type TabKey = "active" | "past";

function credentialStatus(expiry: string | null): string {
  if (!expiry) return "";
  const days = Math.ceil(
    (new Date(expiry).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );
  if (days < 0) return "expired";
  if (days <= 90) return "expiring";
  return "";
}

export default function DashboardPage() {
  const [staff, setStaff] = useState<EmployeeSummary[]>([]);
  const [tab, setTab] = useState<TabKey>("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) { window.location.href = "/login"; return; }
    const user = localStorage.getItem("gatekeep_user");
    if (user) {
      try { setRole(JSON.parse(user).role ?? ""); } catch { /* ignore */ }
    }

    function load() {
      getEmployees(token!)
        .then(setStaff)
        .catch((error) => {
          setError(
            error instanceof Error ? error.message : "Failed to load clinical staff"
          );
        })
        .finally(() => setLoading(false));
    }

    load();

    // Re-fetch whenever the directory regains focus or becomes visible again —
    // so onboarding/offboarding done elsewhere (e.g. via Gary) shows up on return.
    function onFocus() { load(); }
    function onVisible() { if (document.visibilityState === "visible") load(); }
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  function logout() {
    localStorage.removeItem("gatekeep_token");
    localStorage.removeItem("gatekeep_user");
    window.location.href = "/login";
  }

  const active = staff.filter((s) => s.employment_status !== "terminated");
  const past = staff.filter((s) => s.employment_status === "terminated");
  const pool = tab === "active" ? active : past;
  const visible = search.trim()
    ? pool.filter((s) =>
        [s.full_name, s.company_email, s.job_title, s.department]
          .join(" ")
          .toLowerCase()
          .includes(search.toLowerCase())
      )
    : pool;

  const activeAccounts = active.reduce((t, s) => t + s.active_accounts, 0);
  const highRisk = active.filter((s) => s.risk_level === "High").length;

  return (
    <Shell
      actions={
        <Button variant="bare" onClick={logout}>
          Logout
        </Button>
      }
    >
      <PageHeader
        title="Clinical Staff Directory"
        subtitle="Manage clinician identities, system access, and secure offboarding."
        actions={
          <>
            {role === "system_admin" && (
              <Link
                href="/users"
                className="flex h-control items-center gap-2 border border-hairline px-inset font-ui text-ui text-ink transition-colors hover:border-hairline-strong"
              >
                Users
              </Link>
            )}

            <Link
              href="/employees/new"
              className="flex h-control items-center gap-2 border border-hairline px-inset font-ui text-ui text-ink transition-colors hover:border-hairline-strong"
            >
              Add clinician
            </Link>

            <Link
              href="/gary"
              className="flex h-control items-center gap-2 border border-brand bg-brand px-inset font-ui text-ui text-surface transition-colors hover:border-pop hover:bg-pop hover:text-brand"
            >
              Ask Gary
              <ArrowRight size={12} strokeWidth={2} />
            </Link>
          </>
        }
      />

      <div className="mt-8 grid gap-px bg-hairline sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active clinicians" value={active.length} />
        <Stat label="Offboarded" value={past.length} />
        <Stat label="Active system access" value={activeAccounts} />
        <Stat
          label="HIPAA high-risk"
          value={highRisk}
          emphasis={highRisk > 0}
        />
      </div>

      {error ? (
        <div className="mt-8 border border-ink bg-surface p-inset">
          <Caption className="text-ink">{error}</Caption>
          <Caption className="mt-2 text-ink-tertiary">
            Check that the GateKeep Health API is running on port 8000.
          </Caption>
        </div>
      ) : null}

      {!error ? (
        <>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <input
              type="search"
              placeholder="Search by name, email, role…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-control flex-1 border border-hairline bg-surface px-inset font-ui text-ui text-ink placeholder:text-ink-tertiary outline-none focus:border-ink min-w-48"
            />
          </div>

          <div className="mt-4">
            <Tabs
              label="Staff categories"
              value={tab}
              onChange={setTab}
              items={[
                { key: "active", label: "Active", count: active.length },
                { key: "past", label: "Offboarded", count: past.length },
              ]}
            />
          </div>

          <div className="mt-6">
            <Table
              head={
                <>
                  <Th>Clinician</Th>
                  <Th>Unit / Department</Th>
                  <Th>Clinical Role</Th>
                  <Th>License</Th>
                  <Th>Credential Status</Th>
                  <Th>Access</Th>
                  <Th>HIPAA Risk</Th>
                </>
              }
            >
              {loading ? (
                [0, 1, 2].map((row) => (
                  <Tr key={row}>
                    {[0, 1, 2, 3, 4, 5, 6].map((cell) => (
                      <Td key={cell}>
                        <span className="block h-3 w-full max-w-32 bg-sunken" />
                      </Td>
                    ))}
                  </Tr>
                ))
              ) : visible.length === 0 ? (
                <Tr>
                  <Td colSpan={7} className="py-16 text-center text-ink-tertiary">
                    {tab === "active"
                      ? "No active clinical staff."
                      : "No offboarded staff yet."}
                  </Td>
                </Tr>
              ) : (
                visible.map((s) => {
                  const credStatus = credentialStatus(s.credential_expiry);
                  return (
                    <Tr key={s.id} href={`/employees/${s.id}`}>
                      <Td>
                        <Link
                          href={`/employees/${s.id}`}
                          className="font-display text-[16px] text-ink"
                        >
                          {s.full_name}
                        </Link>
                        <div className="mt-1 text-ink-tertiary">
                          {s.company_email}
                        </div>
                      </Td>

                      <Td className="text-ink-secondary">{s.department}</Td>

                      <Td className="text-ink-secondary">{s.job_title}</Td>

                      <Td className="text-ink-secondary">
                        {s.license_type || "—"}
                      </Td>

                      <Td>
                        <Badge level={statusLevel(s.employment_status)}>
                          {s.employment_status.replace("_", " ")}
                        </Badge>
                        {credStatus === "expired" && (
                          <Badge level={4} className="ml-2">expired</Badge>
                        )}
                        {credStatus === "expiring" && (
                          <Badge level={3} className="ml-2">exp. soon</Badge>
                        )}
                      </Td>

                      <Td>
                        {s.active_accounts}/{s.accounts_count}
                      </Td>

                      <Td>
                        <Badge level={scoreLevel(s.risk_score)}>
                          {s.risk_level} · {s.risk_score}
                        </Badge>
                      </Td>
                    </Tr>
                  );
                })
              )}
            </Table>
          </div>
        </>
      ) : null}
    </Shell>
  );
}
