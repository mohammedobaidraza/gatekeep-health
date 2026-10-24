const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

export type EmployeeSummary = {
  id: number;
  full_name: string;
  company_email: string;
  department: string;
  job_title: string;
  manager_name: string | null;
  employment_status: string;
  accounts_count: number;
  active_accounts: number;
  risk_score: number;
  risk_level: string;
  // Healthcare fields
  npi_number: string | null;
  license_type: string | null;
  privilege_level: string;
  credential_expiry: string | null;
};

export type EmployeeDetail = EmployeeSummary & {
  personal_email: string | null;
  start_date: string | null;
  termination_date: string | null;
  last_access_review: string | null;
  active_sessions: number;
  active_credentials: number;
  group_memberships: number;
  owned_assets: number;
  created_at: string;
  updated_at: string;
  // Healthcare detail
  license_number: string | null;
  license_state: string | null;
  dea_number: string | null;
};

export type EmployeeAccount = {
  id: number;
  employee_id: number;
  platform: string;
  account_type: string;
  identifier: string;
  access_level: string;
  status: string;
  last_used_at: string | null;
  risk_level: string;
  revocation_verified: boolean;
  active_sessions: number;
  active_credentials: number;
  metadata: Record<string, unknown>;
};

export type UserRole =
  | "system_admin"
  | "department_head"
  | "staff_coordinator"
  | "compliance_officer";

export type AuthUser = {
  email: string;
  name: string;
  role: UserRole;
  permissions?: Record<string, boolean>;
};

// ── Helpers ────────────────────────────────────────────────────────────────────

async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Response did not contain JSON.
    }
    throw new Error(message);
  }

  return response.json();
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  return apiRequest<{
    access_token: string;
    token_type: string;
    user: AuthUser;
  }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// ── Staff (Employees) ──────────────────────────────────────────────────────────

export async function getEmployees(
  token: string,
  params: { q?: string; department?: string; status?: string } = {}
) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.department) qs.set("department", params.department);
  if (params.status) qs.set("status", params.status);
  const query = qs.toString() ? `?${qs}` : "";
  return apiRequest<EmployeeSummary[]>(`/api/v1/employees${query}`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
}

export async function getEmployee(token: string, employeeId: string) {
  return apiRequest<EmployeeDetail>(`/api/v1/employees/${employeeId}`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
}

export type CreateEmployeeInput = {
  full_name: string;
  company_email: string;
  personal_email?: string;
  department: string;
  job_title: string;
  manager_name?: string;
  start_date?: string;
  employment_status: string;
  auto_provision: boolean;
  access_template: string;
  // Healthcare fields
  npi_number?: string;
  license_number?: string;
  license_state?: string;
  license_type?: string;
  dea_number?: string;
  privilege_level?: string;
  credential_expiry?: string;
};

export async function createEmployee(token: string, input: CreateEmployeeInput) {
  return apiRequest<EmployeeDetail>("/api/v1/employees", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
}

// ── Accounts ───────────────────────────────────────────────────────────────────

export async function getEmployeeAccounts(token: string, employeeId: string) {
  return apiRequest<EmployeeAccount[]>(
    `/api/v1/employees/${employeeId}/accounts`,
    { headers: authHeaders(token), cache: "no-store" }
  );
}

export async function revokeAccount(token: string, accountId: number) {
  return apiRequest<EmployeeAccount>(`/api/v1/accounts/${accountId}/revoke`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason: "Revoked through GateKeep Health" }),
  });
}

export async function verifyAccount(token: string, accountId: number) {
  return apiRequest<{
    account_id: number;
    verified: boolean;
    status: string;
    remaining_sessions: boolean;
    remaining_credentials: boolean;
  }>(`/api/v1/accounts/${accountId}/verify`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function restoreAccount(token: string, accountId: number) {
  return apiRequest<{
    id: number;
    employee_id: number;
    platform: string;
    identifier: string;
    status: string;
    revocation_verified: boolean;
    sessions_restored: boolean;
    credentials_restored: boolean;
    message: string;
  }>(`/api/v1/accounts/${accountId}/restore`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

// ── Termination / Offboarding ──────────────────────────────────────────────────

export async function getTerminationPreview(token: string, employeeId: string) {
  return apiRequest<{
    employee_id: number;
    employee: string;
    accounts_discovered: number;
    active_sessions: number;
    active_credentials: number;
    company_cards: number;
    owned_assets: number;
    actions: Array<{
      account_id: number;
      platform: string;
      identifier: string;
      planned_action: string;
    }>;
  }>(`/api/v1/employees/${employeeId}/termination/preview`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function terminateEmployee(token: string, employeeId: string) {
  return apiRequest<{
    status: string;
    summary: {
      accounts_discovered: number;
      accounts_revoked: number;
      accounts_verified: number;
      requires_manual_action: number;
      sessions_terminated: number;
      tokens_revoked: number;
      company_cards_frozen: number;
      files_transferred: number;
      hidden_access_discovered: number;
    };
  }>(`/api/v1/employees/${employeeId}/terminate`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      preserve_records: true,
      transfer_files_to_manager: true,
      preserve_audit_logs: true,
      reassign_owned_projects: true,
      revoke_sessions: true,
      disable_company_email: true,
      remove_group_memberships: true,
      revoke_system_accounts: true,
      revoke_credentials: true,
      disable_vpn: true,
      remove_cloud_access: true,
      freeze_company_card: true,
      notify_medical_staff_office: true,
      revoke_dea_system_access: true,
      revoke_prescribing_access: true,
    }),
  });
}

export type TerminationSummary = Awaited<
  ReturnType<typeof terminateEmployee>
>["summary"];

export async function reactivateEmployee(token: string, employeeId: string) {
  return apiRequest<{
    status: string;
    employee: EmployeeDetail;
    accounts_restored: number;
    sessions_restored: boolean;
    credentials_restored: boolean;
    message: string;
  }>(`/api/v1/employees/${employeeId}/reactivate`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function getTerminationReport(token: string, employeeId: string) {
  return apiRequest<{
    employee: EmployeeDetail;
    latest_termination: {
      id: number;
      actor: string;
      effective_at: string;
      status: string;
      summary: TerminationSummary;
      created_at: string;
    } | null;
    accounts: EmployeeAccount[];
  }>(`/api/v1/employees/${employeeId}/termination-report`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
}

// ── Assets ─────────────────────────────────────────────────────────────────────

export type CompanyAsset = {
  id: number;
  asset_type: string;
  provider: string;
  identifier: string;
  status: string;
  metadata: Record<string, unknown>;
  assigned_to: string | null;
};

export async function getAssets(token: string, employeeId: string) {
  return apiRequest<CompanyAsset[]>(
    `/api/v1/employees/${employeeId}/assets`,
    { headers: authHeaders(token), cache: "no-store" }
  );
}

export async function freezeAsset(token: string, assetId: number) {
  return apiRequest<{ id: number; status: string }>(
    `/api/v1/assets/${assetId}/freeze`,
    { method: "POST", headers: authHeaders(token) }
  );
}

export async function transferAsset(token: string, assetId: number, assignedTo: string) {
  return apiRequest<{ id: number; status: string; assigned_to: string }>(
    `/api/v1/assets/${assetId}/transfer`,
    {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ assigned_to: assignedTo }),
    }
  );
}

// ── Audit Events ───────────────────────────────────────────────────────────────

export type AuditEvent = {
  id: number;
  actor: string;
  action: string;
  target: string;
  result: string;
  detail: string;
  created_at: string;
};

export async function getAuditEvents(token: string, employeeId: string) {
  return apiRequest<AuditEvent[]>(
    `/api/v1/employees/${employeeId}/audit-events`,
    { headers: authHeaders(token), cache: "no-store" }
  );
}

export function auditExportUrl(employeeId: string) {
  return `${API_URL}/api/v1/employees/${employeeId}/audit-events/export`;
}

// ── System User Management ──────────────────────────────────────────────────────

export type SystemUser = {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
  created_by: string | null;
};

export async function getUsers(token: string) {
  return apiRequest<SystemUser[]>("/api/v1/users", {
    headers: authHeaders(token),
    cache: "no-store",
  });
}

export async function createUser(
  token: string,
  input: { email: string; name: string; password: string; role: UserRole }
) {
  return apiRequest<SystemUser>("/api/v1/users", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
  });
}

export async function updateUser(
  token: string,
  userId: number,
  patch: { name?: string; role?: UserRole; is_active?: boolean }
) {
  return apiRequest<SystemUser>(`/api/v1/users/${userId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(patch),
  });
}

export async function resetUserPassword(token: string, userId: number) {
  return apiRequest<{ status: string; temp_password: string }>(
    `/api/v1/users/${userId}/reset-password`,
    { method: "POST", headers: authHeaders(token) }
  );
}

export async function changePassword(
  token: string,
  currentPassword: string,
  newPassword: string
) {
  return apiRequest<{ status: string }>("/api/v1/auth/change-password", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

// ── Access Templates ───────────────────────────────────────────────────────────

export type AccessTemplate = {
  key: string;
  name: string;
  department: string;
  description: string;
  accounts: Array<{
    platform: string;
    access: string;
    risk: string;
    sessions: number;
    credentials: string[];
  }>;
};

export async function getAccessTemplates(token: string) {
  return apiRequest<AccessTemplate[]>("/api/v1/access-templates", {
    headers: authHeaders(token),
    cache: "no-store",
  });
}

// ── Gary (AI Agent) ───────────────────────────────────────────────────────────

export type GaryAgentStep = {
  sequence: number;
  stage: "parse" | "resolve" | "plan" | "execute" | "verify" | "report";
  status: "pending" | "running" | "completed" | "verified" | "failed" | "needs_input";
  message: string;
  evidence: Record<string, unknown>;
};

export type AccessPlatform = {
  platform: string;
  access_level: string;
  status: string;
  identifier: string;
  risk_level?: string;
};

export type AccessGroup = {
  label: string;
  category: string;
  platforms: AccessPlatform[];
};

export type GaryAgentResult = {
  run_id: string;
  intent: "onboard_employee" | "offboard_employee" | "unknown";
  status: "planned" | "completed" | "failed" | "needs_input";
  employee_id: number | null;
  employee_name: string | null;
  confidence: number;
  steps: GaryAgentStep[];
  summary: Record<string, unknown>;
  message: string;
  access_groups?: AccessGroup[];
  access_action?: "granted" | "revoked" | null;
};

export async function runGaryAgent(
  token: string,
  instruction: string,
  autoExecute = true
): Promise<GaryAgentResult> {
  return apiRequest<GaryAgentResult>("/api/v1/agent/run", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ instruction, auto_execute: autoExecute }),
  });
}

// ── Gary streaming (SSE via fetch ReadableStream) ─────────────────────────────

export type GaryStreamEvent =
  | { type: "step"; step: GaryAgentStep }
  | { type: "done"; result: GaryAgentResult }
  | { type: "error"; message: string };

export async function* streamGaryAgent(
  token: string,
  instruction: string,
  autoExecute = true
): AsyncGenerator<GaryStreamEvent> {
  const response = await fetch(`${API_URL}/api/v1/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ instruction, auto_execute: autoExecute }),
  });
  if (!response.ok) {
    throw new Error(`Gary stream failed: ${response.status}`);
  }
  if (!response.body) throw new Error("No response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const raw = line.slice(6).trim();
        if (raw) {
          try {
            yield JSON.parse(raw) as GaryStreamEvent;
          } catch {
            // malformed chunk — skip
          }
        }
      }
    }
  }
}
