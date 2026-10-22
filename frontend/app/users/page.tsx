"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { LabeledInput } from "@/components/ui/Field";
import { Caption, PanelTitle } from "@/components/ui/Panel";
import { PageHeader, Shell } from "@/components/ui/Shell";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import {
  SystemUser,
  UserRole,
  createUser,
  getUsers,
  resetUserPassword,
  updateUser,
} from "@/lib/api";

const ROLE_LABELS: Record<UserRole, string> = {
  system_admin: "System Admin",
  department_head: "Department Head",
  staff_coordinator: "Staff Coordinator",
  compliance_officer: "Compliance Officer",
};

const ROLES: UserRole[] = [
  "system_admin",
  "department_head",
  "staff_coordinator",
  "compliance_officer",
];

export default function UsersPage() {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "staff_coordinator" as UserRole,
  });
  const [creating, setCreating] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("gatekeep_token") ?? "" : "";

  useEffect(() => {
    if (!localStorage.getItem("gatekeep_token")) {
      window.location.href = "/login";
      return;
    }
    load();
  }, []);

  async function load() {
    try {
      setUsers(await getUsers(token));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setMessage("");
    try {
      await createUser(token, form);
      setForm({ name: "", email: "", password: "", role: "staff_coordinator" });
      setShowCreate(false);
      setMessage(`User ${form.email} created. A welcome email has been sent.`);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(user: SystemUser) {
    setBusy(user.id);
    try {
      await updateUser(token, user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setBusy(null);
    }
  }

  async function handleResetPassword(user: SystemUser) {
    setBusy(user.id);
    try {
      const result = await resetUserPassword(token, user.id);
      setMessage(`Temporary password for ${user.email}: ${result.temp_password}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setBusy(null);
    }
  }

  async function handleRoleChange(user: SystemUser, role: UserRole) {
    setBusy(user.id);
    try {
      await updateUser(token, user.id, { role });
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update role");
    } finally {
      setBusy(null);
    }
  }

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
        title="System Users"
        subtitle="Manage who can log into GateKeep Health and what they can do."
        actions={
          <Button variant="solid" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "Add user"}
          </Button>
        }
      />

      {message && (
        <Caption className="mt-6 bg-surface p-inset font-mono text-ink">{message}</Caption>
      )}

      {showCreate && (
        <section className="mt-8 bg-surface p-inset">
          <PanelTitle>New user</PanelTitle>
          <form onSubmit={handleCreate} className="mt-6 flex flex-col gap-6">
            <div className="grid gap-6 sm:grid-cols-2">
              <LabeledInput
                label="Full name"
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
              <LabeledInput
                label="Email"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
              <LabeledInput
                label="Temporary password"
                type="text"
                required
                hint="Min 8 characters. User must change on first login."
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
              <div>
                <span className="block font-ui text-ui text-ink-tertiary">Role</span>
                <div className="mt-2 flex flex-col gap-1 bg-surface">
                  {ROLES.map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, role: r }))}
                      className={`flex w-full items-center gap-3 border-b border-hairline px-inset py-3 text-left last:border-b-0 ${
                        form.role === r ? "bg-sunken" : "hover:bg-sunken"
                      }`}
                    >
                      <span className={`font-ui text-ui ${form.role === r ? "text-ink" : "text-ink-secondary"}`}>
                        {ROLE_LABELS[r]}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div>
              <Button type="submit" variant="solid" disabled={creating}>
                {creating ? "Creating…" : "Create user"}
              </Button>
            </div>
          </form>
        </section>
      )}

      <div className="mt-8">
        <Table
          head={
            <>
              <Th>Name</Th>
              <Th>Email</Th>
              <Th>Role</Th>
              <Th>Status</Th>
              <Th>Last login</Th>
              <Th />
            </>
          }
        >
          {loading ? (
            [0, 1, 2, 3].map((row) => (
              <Tr key={row}>
                {[0, 1, 2, 3, 4, 5].map((cell) => (
                  <Td key={cell}><span className="block h-3 w-full max-w-32 bg-sunken" /></Td>
                ))}
              </Tr>
            ))
          ) : (
            users.map((u) => (
              <Tr key={u.id}>
                <Td>
                  <span className="font-display text-[16px] text-ink">{u.name}</span>
                  {u.must_change_password && (
                    <span className="ml-2 font-ui text-ui text-ink-tertiary">(must change pw)</span>
                  )}
                </Td>
                <Td className="text-ink-tertiary">{u.email}</Td>
                <Td>
                  <select
                    value={u.role}
                    disabled={busy === u.id}
                    onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
                    className="border border-hairline bg-surface px-2 py-1 font-ui text-ui text-ink focus:outline-none"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                    ))}
                  </select>
                </Td>
                <Td className={u.is_active ? "text-ink-secondary" : "text-ink-tertiary"}>
                  {u.is_active ? "Active" : "Deactivated"}
                </Td>
                <Td className="text-ink-tertiary">
                  {u.last_login_at
                    ? new Date(u.last_login_at).toLocaleDateString()
                    : "Never"}
                </Td>
                <Td>
                  <div className="flex items-center gap-4">
                    <Button
                      variant="bare"
                      disabled={busy === u.id}
                      onClick={() => handleToggle(u)}
                      className="h-auto px-0"
                    >
                      {busy === u.id ? "Working" : u.is_active ? "Deactivate" : "Reactivate"}
                    </Button>
                    <Button
                      variant="bare"
                      disabled={busy === u.id}
                      onClick={() => handleResetPassword(u)}
                      className="h-auto px-0"
                    >
                      Reset password
                    </Button>
                  </div>
                </Td>
              </Tr>
            ))
          )}
        </Table>
      </div>
    </Shell>
  );
}
