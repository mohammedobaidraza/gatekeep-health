"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Badge, riskLevel } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LabeledInput } from "@/components/ui/Field";
import { Caption, PanelTitle } from "@/components/ui/Panel";
import { PageHeader, Shell } from "@/components/ui/Shell";
import { AccessTemplate, createEmployee, getAccessTemplates } from "@/lib/api";

type FormState = {
  full_name: string;
  company_email: string;
  personal_email: string;
  job_title: string;
  manager_name: string;
  start_date: string;
  access_template: string;
  // Healthcare fields
  npi_number: string;
  license_number: string;
  license_state: string;
  license_type: string;
  dea_number: string;
  privilege_level: string;
  credential_expiry: string;
};

const initialForm: FormState = {
  full_name: "",
  company_email: "",
  personal_email: "",
  job_title: "",
  manager_name: "",
  start_date: new Date().toISOString().split("T")[0],
  access_template: "physician",
  npi_number: "",
  license_number: "",
  license_state: "",
  license_type: "",
  dea_number: "",
  privilege_level: "standard",
  credential_expiry: "",
};

const LICENSE_TYPES = ["MD", "DO", "RN", "LPN", "NP", "PA", "PharmD", "RT", "DDS", "Other"];
const PRIVILEGE_LEVELS = [
  { value: "full",       label: "Full privileges" },
  { value: "limited",    label: "Limited privileges" },
  { value: "supervised", label: "Supervised (trainee)" },
  { value: "standard",   label: "Standard (non-clinical)" },
];

export default function NewEmployeePage() {
  const router = useRouter();

  const [templates, setTemplates] = useState<AccessTemplate[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("gatekeep_token");
    if (!token) { window.location.href = "/login"; return; }

    let cancelled = false;
    getAccessTemplates(token)
      .then((data) => { if (!cancelled) { setTemplates(data); setLoading(false); } })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Failed to load role templates");
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(
    () => templates.find((t) => t.key === form.access_template),
    [templates, form.access_template]
  );

  function update(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function selectTemplate(template: AccessTemplate) {
    setForm((current) => ({
      ...current,
      access_template: template.key,
      job_title:
        !current.job_title || templates.some((t) => t.name === current.job_title)
          ? template.name
          : current.job_title,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = localStorage.getItem("gatekeep_token");
    if (!token) { window.location.href = "/login"; return; }
    if (!selected) { setError("Select a clinical role."); return; }

    setSubmitting(true);
    setError("");

    try {
      const clinician = await createEmployee(token, {
        full_name: form.full_name,
        company_email: form.company_email,
        personal_email: form.personal_email || undefined,
        department: selected.department,
        job_title: form.job_title || selected.name,
        manager_name: form.manager_name || undefined,
        start_date: form.start_date || undefined,
        employment_status: "active",
        auto_provision: true,
        access_template: selected.key,
        npi_number: form.npi_number || undefined,
        license_number: form.license_number || undefined,
        license_state: form.license_state || undefined,
        license_type: form.license_type || undefined,
        dea_number: form.dea_number || undefined,
        privilege_level: form.privilege_level || undefined,
        credential_expiry: form.credential_expiry || undefined,
      });
      router.push(`/employees/${clinician.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to credential clinician");
      setSubmitting(false);
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
        title="Add clinician"
        subtitle="Select a clinical role, review what it grants, and provision all system access in one step."
      />

      {loading ? (
        <Caption className="mt-8">Loading clinical role templates…</Caption>
      ) : (
        <form onSubmit={handleSubmit} className="mt-8">
          <div className="grid gap-10 lg:grid-cols-[1fr_1fr]">
            {/* Left — Role + preview */}
            <div className="flex flex-col gap-10">
              <section>
                <PanelTitle>Clinical role</PanelTitle>
                <Caption className="mt-2 text-ink-tertiary">
                  Determines the department and the clinical systems provisioned.
                </Caption>

                <div className="mt-4 bg-surface">
                  {templates.map((template) => {
                    const active = template.key === form.access_template;
                    return (
                      <button
                        key={template.key}
                        type="button"
                        aria-pressed={active}
                        onClick={() => selectTemplate(template)}
                        className={`flex w-full flex-col gap-1 border-b border-l-2 border-hairline px-inset py-4 text-left transition-colors last:border-b-0 ${
                          active
                            ? "border-l-pop bg-sunken"
                            : "border-l-transparent hover:bg-sunken"
                        }`}
                      >
                        <span className="flex items-baseline justify-between gap-4">
                          <span className={`font-ui text-ui ${active ? "text-ink" : "text-ink-secondary"}`}>
                            {template.name}
                          </span>
                          <span className="font-ui text-ui text-ink-tertiary">
                            {template.accounts.length} systems
                          </span>
                        </span>
                        <span className="font-ui text-ui leading-5 text-ink-tertiary">
                          {template.description}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>

              {selected ? (
                <section>
                  <PanelTitle>Systems to be provisioned</PanelTitle>
                  <Caption className="mt-2 text-ink-tertiary">
                    {selected.department} · {selected.accounts.length} clinical systems
                  </Caption>

                  <div className="mt-4 bg-surface">
                    {selected.accounts.map((account) => (
                      <div
                        key={account.platform}
                        className="flex items-center justify-between gap-4 border-b border-hairline px-inset py-3 last:border-b-0"
                      >
                        <div className="flex flex-col gap-1">
                          <span className="font-ui text-ui text-ink">{account.platform}</span>
                          <span className="font-ui text-ui text-ink-tertiary">
                            {account.access}
                            {account.credentials.length > 0
                              ? ` · ${account.credentials.join(", ")}`
                              : ""}
                          </span>
                        </div>
                        <Badge level={riskLevel(account.risk)}>{account.risk}</Badge>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>

            {/* Right — Details */}
            <section>
              <PanelTitle>Identity & credentials</PanelTitle>
              <Caption className="mt-2 text-ink-tertiary">
                Company email becomes the identity across every provisioned clinical system.
              </Caption>

              <div className="mt-4 flex flex-col gap-6 bg-surface p-inset">
                <LabeledInput
                  label="Full name"
                  required
                  value={form.full_name}
                  onChange={(e) => update("full_name", e.target.value)}
                />
                <LabeledInput
                  label="Company email"
                  type="email"
                  required
                  value={form.company_email}
                  onChange={(e) => update("company_email", e.target.value)}
                />
                <LabeledInput
                  label="Personal email"
                  type="email"
                  hint="Used to reach them after offboarding."
                  value={form.personal_email}
                  onChange={(e) => update("personal_email", e.target.value)}
                />
                <LabeledInput
                  label="Job title"
                  required
                  value={form.job_title}
                  onChange={(e) => update("job_title", e.target.value)}
                />
                <LabeledInput
                  label="Supervisor / Manager"
                  hint="Patient records transfer here if offboarded."
                  value={form.manager_name}
                  onChange={(e) => update("manager_name", e.target.value)}
                />
                <LabeledInput
                  label="Start date"
                  type="date"
                  value={form.start_date}
                  onChange={(e) => update("start_date", e.target.value)}
                />
              </div>

              {/* Healthcare credential fields */}
              <PanelTitle className="mt-8">Licensure & credentialing</PanelTitle>
              <Caption className="mt-2 text-ink-tertiary">
                Required for prescribers, licensed clinicians, and DEA registrants.
              </Caption>

              <div className="mt-4 flex flex-col gap-6 bg-surface p-inset">
                <LabeledInput
                  label="NPI number"
                  hint="10-digit National Provider Identifier."
                  value={form.npi_number}
                  onChange={(e) => update("npi_number", e.target.value)}
                />

                <div className="grid grid-cols-2 gap-4">
                  <LabeledInput
                    label="License number"
                    value={form.license_number}
                    onChange={(e) => update("license_number", e.target.value)}
                  />
                  <LabeledInput
                    label="License state"
                    hint="2-letter code, e.g. CA"
                    value={form.license_state}
                    onChange={(e) => update("license_state", e.target.value.toUpperCase().slice(0, 2))}
                  />
                </div>

                <div>
                  <span className="block font-ui text-ui text-ink-tertiary">License type</span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {LICENSE_TYPES.map((lt) => (
                      <button
                        key={lt}
                        type="button"
                        onClick={() => update("license_type", lt === form.license_type ? "" : lt)}
                        className={`border px-3 py-1 font-ui text-ui transition-colors ${
                          form.license_type === lt
                            ? "border-brand bg-brand text-surface"
                            : "border-hairline text-ink-secondary hover:border-hairline-strong"
                        }`}
                      >
                        {lt}
                      </button>
                    ))}
                  </div>
                </div>

                <LabeledInput
                  label="DEA number"
                  hint="Required for prescribers and pharmacists."
                  value={form.dea_number}
                  onChange={(e) => update("dea_number", e.target.value)}
                />

                <div>
                  <span className="block font-ui text-ui text-ink-tertiary">Privilege level</span>
                  <div className="mt-2 flex flex-col gap-1 bg-surface">
                    {PRIVILEGE_LEVELS.map((pl) => (
                      <button
                        key={pl.value}
                        type="button"
                        onClick={() => update("privilege_level", pl.value)}
                        className={`flex w-full items-center gap-3 border-b border-hairline px-inset py-3 text-left transition-colors last:border-b-0 ${
                          form.privilege_level === pl.value
                            ? "bg-sunken"
                            : "hover:bg-sunken"
                        }`}
                      >
                        <span className={`font-ui text-ui ${
                          form.privilege_level === pl.value ? "text-ink" : "text-ink-secondary"
                        }`}>
                          {pl.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <LabeledInput
                  label="Credential expiry"
                  type="date"
                  hint="When the license or privileging expires."
                  value={form.credential_expiry}
                  onChange={(e) => update("credential_expiry", e.target.value)}
                />
              </div>

              {error ? (
                <Caption className="mt-4 text-ink">{error}</Caption>
              ) : null}

              <div className="mt-6 flex items-center gap-4">
                <Button
                  type="submit"
                  variant="solid"
                  icon={ArrowRight}
                  disabled={submitting}
                >
                  {submitting
                    ? "Credentialing"
                    : `Credential and provision ${selected?.accounts.length ?? 0} systems`}
                </Button>

                <Link
                  href="/dashboard"
                  className="font-ui text-ui text-ink-secondary transition-colors hover:text-ink"
                >
                  Cancel
                </Link>
              </div>
            </section>
          </div>
        </form>
      )}
    </Shell>
  );
}
