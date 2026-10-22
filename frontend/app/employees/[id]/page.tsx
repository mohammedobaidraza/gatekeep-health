"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Verified,
  riskLevel,
  scoreLevel,
  statusLevel,
} from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Caption, PanelTitle } from "@/components/ui/Panel";
import { PageHeader, Shell } from "@/components/ui/Shell";
import { Stat } from "@/components/ui/Stat";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import {
  auditExportUrl,
  getAssets,
  getAuditEvents,
  getEmployee,
  getEmployeeAccounts,
  reactivateEmployee,
  restoreAccount,
  revokeAccount,
  verifyAccount,
  type AuditEvent,
  type CompanyAsset,
  type EmployeeAccount,
  type EmployeeDetail,
} from "@/lib/api";
import { ActivityLog } from "./ActivityLog";
import { AssetsPanel } from "./AssetsPanel";

const RISK_ORDER = ["critical", "high", "medium", "low"];

function byRisk(a: EmployeeAccount, b: EmployeeAccount) {
  const rank =
    RISK_ORDER.indexOf(a.risk_level.toLowerCase()) -
    RISK_ORDER.indexOf(b.risk_level.toLowerCase());
  return rank !== 0 ? rank : a.platform.localeCompare(b.platform);
}

export default function EmployeePage() {
  const params = useParams<{ id: string }>();
  const employeeId = params.id;

  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [accounts, setAccounts] = useState<EmployeeAccount[]>([]);
  const [assets, setAssets] = useState<CompanyAsset[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [busyAccount, setBusyAccount] = useState<number | null>(null);
  const [reactivating, setReactivating] = useState(false);

  const load = useCallback(async () => {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) { window.location.href = "/login"; return; }

    const [employeeResponse, accountsResponse, assetsResponse, eventsResponse] =
      await Promise.all([
        getEmployee(token, employeeId),
        getEmployeeAccounts(token, employeeId),
        getAssets(token, employeeId),
        getAuditEvents(token, employeeId),
      ]);

    setEmployee(employeeResponse);
    setAccounts([...accountsResponse].sort(byRisk));
    setAssets(assetsResponse);
    setEvents(eventsResponse);
  }, [employeeId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await load();
      } catch {
        if (!cancelled) setMessage("Failed to load clinician");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [load]);

  async function handleRevoke(accountId: number) {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) return;
    setBusyAccount(accountId);
    try {
      await revokeAccount(token, accountId);
      const verification = await verifyAccount(token, accountId);
      setMessage(
        verification.verified
          ? "Access revoked and verified closed."
          : "Access changed, but verification did not pass."
      );
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to revoke access");
    } finally {
      setBusyAccount(null);
    }
  }

  async function handleRestore(accountId: number) {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) return;
    setBusyAccount(accountId);
    try {
      const result = await restoreAccount(token, accountId);
      setMessage(result.message);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to restore access");
    } finally {
      setBusyAccount(null);
    }
  }

  async function handleReactivate() {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) return;
    setReactivating(true);
    try {
      const result = await reactivateEmployee(token, employeeId);
      setMessage(result.message);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to restore credentials");
    } finally {
      setReactivating(false);
    }
  }

  if (loading) {
    return (
      <Shell>
        <Caption>Loading clinician…</Caption>
      </Shell>
    );
  }

  if (!employee) {
    return (
      <Shell>
        <PanelTitle>Clinician not found</PanelTitle>
        <Caption className="mt-2">{message}</Caption>
      </Shell>
    );
  }

  const terminated = employee.employment_status === "terminated";

  return (
    <Shell
      actions={
        <Link
          href="/dashboard"
          className="flex items-center gap-2 font-ui text-ui text-ink-secondary transition-colors hover:text-ink"
        >
          <ArrowLeft size={12} strokeWidth={2} />
          Directory
        </Link>
      }
    >
      <PageHeader
        title={employee.full_name}
        subtitle={`${employee.department} · ${employee.job_title} · Supervisor: ${employee.manager_name || "Not assigned"}`}
        actions={
          terminated ? (
            <>
              <Button
                variant="outline"
                disabled={reactivating}
                onClick={handleReactivate}
              >
                {reactivating ? "Restoring credentials" : "Restore credentials"}
              </Button>

              <Link
                href={`/employees/${employeeId}/report`}
                className="flex h-control items-center gap-2 border border-brand bg-brand px-inset font-ui text-ui text-surface transition-colors hover:border-pop hover:bg-pop hover:text-brand"
              >
                View offboard report
                <ArrowRight size={12} strokeWidth={2} />
              </Link>
            </>
          ) : (
            <Link
              href={`/employees/${employeeId}/offboard`}
              className="flex h-control items-center gap-2 border border-brand bg-brand px-inset font-ui text-ui text-surface transition-colors hover:border-pop hover:bg-pop hover:text-brand"
            >
              Offboard clinician
              <ArrowRight size={12} strokeWidth={2} />
            </Link>
          )
        }
      />

      {message ? (
        <Caption className="mt-6 bg-surface p-inset text-ink">{message}</Caption>
      ) : null}

      <div className="mt-8 grid gap-px bg-hairline sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="HIPAA risk score"
          value={employee.risk_score}
          hint={`${employee.risk_level} · out of 100`}
          emphasis={scoreLevel(employee.risk_score) === 4}
        />
        <Stat label="Active system access" value={employee.active_accounts} />
        <Stat label="Active sessions" value={employee.active_sessions} />
        <Stat label="Active credentials" value={employee.active_credentials} />
      </div>

      {/* Clinician information */}
      <section className="mt-10 bg-surface p-inset">
        <PanelTitle>Clinician information</PanelTitle>

        <div className="mt-6 grid gap-6 md:grid-cols-3">
          <Info label="Company email" value={employee.company_email} />
          <Info label="Personal email" value={employee.personal_email || "Not provided"} />
          <Info label="Credential status" value={employee.employment_status.replace("_", " ")} />
          <Info label="Start date" value={employee.start_date || "Not provided"} />
          <Info label="Owned assets" value={String(employee.owned_assets)} />
          <Info
            label="Last access review"
            value={
              employee.last_access_review
                ? new Date(employee.last_access_review).toLocaleDateString()
                : "Never reviewed"
            }
          />
        </div>

        {/* Healthcare credential info */}
        {(employee.npi_number || employee.license_number || employee.dea_number) ? (
          <>
            <div className="mt-6 border-t border-hairline pt-6">
              <span className="block font-ui text-ui text-ink-tertiary">Licensure</span>
            </div>
            <div className="mt-4 grid gap-6 md:grid-cols-3">
              {employee.npi_number ? (
                <Info label="NPI number" value={employee.npi_number} />
              ) : null}
              {employee.license_type ? (
                <Info label="License type" value={employee.license_type} />
              ) : null}
              {employee.license_number ? (
                <Info
                  label="License"
                  value={`${employee.license_number}${employee.license_state ? ` (${employee.license_state})` : ""}`}
                />
              ) : null}
              {employee.dea_number ? (
                <Info label="DEA number" value={employee.dea_number} />
              ) : null}
              {employee.privilege_level ? (
                <Info label="Privilege level" value={employee.privilege_level} />
              ) : null}
              {employee.credential_expiry ? (
                <Info label="Credential expiry" value={employee.credential_expiry} />
              ) : null}
            </div>
          </>
        ) : null}
      </section>

      {/* Clinical system access */}
      <section className="mt-10">
        <PanelTitle>Clinical system access</PanelTitle>

        <Caption className="mt-2 text-ink-tertiary">
          Sorted by risk. Revoke individually, or offboard to close every access path at once.
        </Caption>

        <div className="mt-4">
          <Table
            minWidth={980}
            head={
              <>
                <Th>System</Th>
                <Th>Identifier</Th>
                <Th>Access level</Th>
                <Th>Risk</Th>
                <Th>Sessions</Th>
                <Th>Credentials</Th>
                <Th>Status</Th>
                <Th />
              </>
            }
          >
            {accounts.map((account) => {
              const isActive = account.status === "active";
              return (
                <Tr key={account.id}>
                  <Td>
                    <span className="font-display text-[16px] text-ink">{account.platform}</span>
                  </Td>
                  <Td className="text-ink-tertiary">{account.identifier}</Td>
                  <Td className="text-ink-secondary">{account.access_level}</Td>
                  <Td>
                    <Badge level={riskLevel(account.risk_level)}>{account.risk_level}</Badge>
                  </Td>
                  <Td>{account.active_sessions}</Td>
                  <Td>{account.active_credentials}</Td>
                  <Td>
                    <div className="flex items-center gap-3">
                      <Badge level={statusLevel(account.status)}>{account.status}</Badge>
                      {account.revocation_verified ? <Verified /> : null}
                    </div>
                  </Td>
                  <Td>
                    <Button
                      variant="bare"
                      disabled={busyAccount === account.id}
                      onClick={() =>
                        isActive ? handleRevoke(account.id) : handleRestore(account.id)
                      }
                      className="h-auto px-0"
                    >
                      {busyAccount === account.id
                        ? "Working"
                        : isActive
                          ? "Revoke"
                          : "Restore"}
                    </Button>
                  </Td>
                </Tr>
              );
            })}
          </Table>
        </div>
      </section>

      <div className="mt-10">
        <AssetsPanel assets={assets} managerName={employee.manager_name} onChange={load} />
      </div>

      <div className="mt-10">
        <ActivityLog events={events} />
        <div className="mt-4">
          <a
            href={`${auditExportUrl(employeeId)}?token=${localStorage.getItem("gatekeep_token") ?? ""}`}
            download
            className="font-ui text-ui text-ink-tertiary underline decoration-hairline underline-offset-4 transition-colors hover:text-ink"
            onClick={(e) => {
              // Use Authorization header approach via fetch for proper auth
              e.preventDefault();
              const token = localStorage.getItem("gatekeep_token");
              fetch(auditExportUrl(employeeId), { headers: { Authorization: `Bearer ${token}` } })
                .then((r) => r.blob())
                .then((blob) => {
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `audit-${employeeId}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                });
            }}
          >
            Export audit log (CSV)
          </a>
        </div>
      </div>
    </Shell>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-ui text-ui text-ink-tertiary">{label}</span>
      <span className="font-ui text-ui text-ink">{value}</span>
    </div>
  );
}
