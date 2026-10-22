"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Verified } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Caption, PanelTitle } from "@/components/ui/Panel";
import { PageHeader, Shell } from "@/components/ui/Shell";
import { GaryAgentResult, GaryAgentStep, streamGraceAgent } from "@/lib/api";

const EXAMPLES = [
  {
    label: "Credential a physician",
    text: "Add Dr. Layla Hassan as an attending physician. Her email is layla.hassan@cityhealth.org. Her supervisor is Dr. Michael Roberts.",
  },
  {
    label: "Credential a nurse",
    text: "Onboard Sarah Kim as a registered nurse in the ICU. Her email is sarah.kim@cityhealth.org and her license number is RN-CA-44201.",
  },
  {
    label: "Offboard immediately",
    text: "Offboard Nurse James Torres immediately. Revoke all clinical system access, preserve patient records per HIPAA, and notify the department head.",
  },
  {
    label: "Scheduled offboarding",
    text: "Schedule the offboarding of Dr. Fatima Al-Rashid for her last day, December 31. Preserve all patient records and transfer files to her supervisor.",
  },
];

const STAGE_LABELS: Record<GaryAgentStep["stage"], string> = {
  parse: "Understand the instruction",
  resolve: "Resolve the clinician",
  plan: "Build the access plan",
  execute: "Execute the workflow",
  verify: "Verify the final state",
  report: "Write the report",
};

const PENDING_STAGES: GaryAgentStep["stage"][] = [
  "parse",
  "resolve",
  "plan",
  "execute",
  "verify",
];

const INTENT_LABELS: Record<GaryAgentResult["intent"], string> = {
  onboard_employee: "Credentialing",
  offboard_employee: "Offboarding",
  unknown: "Unrecognised",
};

function titleCase(key: string) {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function GracePage() {
  const [instruction, setInstruction] = useState("");
  const [result, setResult] = useState<GaryAgentResult | null>(null);
  const [liveSteps, setLiveSteps] = useState<GaryAgentStep[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("gatekeep_token")) {
      window.location.href = "/login";
    }
  }, []);

  async function run() {
    const cleaned = instruction.trim();
    if (!cleaned) { setError("Enter a credentialing or offboarding instruction."); return; }

    const token = localStorage.getItem("gatekeep_token");
    if (!token) { window.location.href = "/login"; return; }

    setRunning(true);
    setError("");
    setResult(null);
    setLiveSteps([]);

    try {
      for await (const event of streamGraceAgent(token, cleaned, true)) {
        if (event.type === "step") {
          setLiveSteps((prev) => {
            const next = prev.filter((s) => s.sequence !== event.step.sequence);
            return [...next, event.step].sort((a, b) => a.sequence - b.sequence);
          });
        } else if (event.type === "done") {
          setResult(event.result);
        } else if (event.type === "error") {
          setError(event.message);
        }
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Grace could not complete the request.");
    } finally {
      setRunning(false);
    }
  }

  const steps = result?.steps ?? liveSteps;

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
        title="Grace"
        subtitle="Describe a credentialing or offboarding in plain language. Grace works out the intent, executes it, and verifies the result."
      />

      <div className="mt-8 bg-surface p-inset">
        <label htmlFor="instruction" className="font-ui text-ui text-ink-tertiary">
          Instruction
        </label>

        <textarea
          id="instruction"
          rows={6}
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="Offboard Nurse James Torres immediately. Revoke all clinical system access and preserve patient records per HIPAA."
          className="mt-2 w-full resize-y border border-hairline p-inset font-ui text-ui leading-6 text-ink outline-none transition-colors focus:border-ink"
        />

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <span className="font-ui text-ui text-ink-tertiary">Try</span>
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setInstruction(example.text)}
              className="font-ui text-ui text-ink-secondary underline decoration-hairline underline-offset-4 transition-colors hover:text-ink"
            >
              {example.label}
            </button>
          ))}
        </div>

        {error ? <Caption className="mt-4 text-ink">{error}</Caption> : null}

        <div className="mt-6">
          <Button variant="solid" icon={ArrowRight} disabled={running} onClick={run}>
            {running ? "Grace is working" : "Run Grace"}
          </Button>
        </div>
      </div>

      {(running || result) && (running || result?.intent !== "unknown") ? (
        <section className="mt-10">
          <PanelTitle>{running ? "Working" : "Execution timeline"}</PanelTitle>

          <div className="mt-4 bg-surface">
            {steps.length > 0
              ? [...steps]
                  .sort((a, b) => a.sequence - b.sequence)
                  .map((step, index) => (
                    <StageRow
                      key={`${step.sequence}-${step.stage}`}
                      index={index}
                      label={STAGE_LABELS[step.stage] ?? step.stage}
                      step={step}
                    />
                  ))
              : PENDING_STAGES.map((stage, index) => (
                  <StageRow key={stage} index={index} label={STAGE_LABELS[stage]} />
                ))}
          </div>
        </section>
      ) : null}

      {result ? (
        result.intent === "unknown" ? (
          <UnknownResult onUse={(text) => setInstruction(text)} />
        ) : (
          <>
            <section className="mt-10">
              <PanelTitle>{result.message}</PanelTitle>

              <div className="mt-4 grid gap-px bg-hairline sm:grid-cols-4">
                <Figure label="Intent" value={INTENT_LABELS[result.intent]} />
                <Figure label="Status" value={result.status.replace("_", " ")} />
                <Figure label="Confidence" value={`${Math.round(result.confidence * 100)}%`} />
                <Figure label="Run" value={result.run_id.slice(0, 8)} />
              </div>

              {result.employee_name ? (
                <Caption className="mt-4 text-ink-tertiary">
                  Clinician: {result.employee_name}
                </Caption>
              ) : null}
            </section>

            {Object.keys(result.summary).length > 0 ? (
              <section className="mt-10">
                <PanelTitle>Proof of work</PanelTitle>
                <div className="mt-4 grid gap-px bg-hairline sm:grid-cols-3">
                  {Object.entries(result.summary).map(([key, value]) => (
                    <Figure key={key} label={titleCase(key)} value={String(value)} />
                  ))}
                </div>
              </section>
            ) : null}

            <div className="mt-8 flex flex-wrap items-center gap-4">
              {result.employee_id ? (
                <Link
                  href={`/employees/${result.employee_id}`}
                  className="flex h-control items-center gap-2 border border-brand bg-brand px-inset font-ui text-ui text-surface transition-colors hover:border-pop hover:bg-pop hover:text-brand"
                >
                  View clinician
                  <ArrowRight size={12} strokeWidth={2} />
                </Link>
              ) : null}

              <Link
                href="/dashboard"
                className="font-ui text-ui text-ink-secondary transition-colors hover:text-ink"
              >
                Back to directory
              </Link>
            </div>
          </>
        )
      ) : null}
    </Shell>
  );
}

function StageRow({
  index,
  label,
  step,
}: {
  index: number;
  label: string;
  step?: GaryAgentStep;
}) {
  const muted = !step;
  return (
    <div className="flex items-start justify-between gap-6 border-b border-hairline px-inset py-4 last:border-b-0">
      <div className="flex items-start gap-4">
        <span className={`font-ui text-ui tabular-nums ${muted ? "text-ink-tertiary" : "text-ink-secondary"}`}>
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="flex flex-col gap-1">
          <span className={`font-ui text-ui ${muted ? "text-ink-tertiary" : "text-ink"}`}>
            {label}
          </span>
          {step?.message ? (
            <span className="font-ui text-ui leading-5 text-ink-tertiary">{step.message}</span>
          ) : null}
        </div>
      </div>

      {step?.status === "verified" ? (
        <Verified />
      ) : (
        <span className={`font-ui text-ui whitespace-nowrap ${step?.status === "failed" ? "text-ink" : "text-ink-tertiary"}`}>
          {step ? step.status.replace("_", " ") : "—"}
        </span>
      )}
    </div>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-2 bg-surface p-inset">
      <span className="font-ui text-ui text-ink-tertiary">{label}</span>
      <span className="font-display text-[24px] leading-none break-words">{value}</span>
    </div>
  );
}

const CAPABILITIES = [
  {
    heading: "Credential a clinician",
    examples: [
      "Add Dr. Layla Hassan as an attending physician. Her email is layla.hassan@cityhealth.org.",
      "Onboard Sarah Kim as a registered nurse. License RN-CA-44201. Supervisor is Charge Nurse Patricia Kim.",
      "Add a new pharmacist — Dr. Omar Farouk, email omar.farouk@cityhealth.org, DEA number BF1234567.",
    ],
  },
  {
    heading: "Offboard a clinician",
    examples: [
      "Offboard Nurse James Torres immediately. Revoke all clinical system access and preserve patient records per HIPAA.",
      "Schedule the offboarding of Dr. Sarah Chen for December 31. Transfer files to Dr. Roberts.",
      "Terminate Dr. Fatima Al-Rashid's access today. Revoke DEA system access and notify the medical staff office.",
    ],
  },
];

function UnknownResult({ onUse }: { onUse: (text: string) => void }) {
  return (
    <section className="mt-10">
      <PanelTitle>Grace handles two things</PanelTitle>
      <Caption className="mt-2 text-ink-tertiary">
        Describe the action in plain language — Grace works out the details, executes it, and verifies the result. Here are some examples to get started.
      </Caption>

      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        {CAPABILITIES.map((cap) => (
          <div key={cap.heading} className="bg-surface">
            <div className="border-b border-hairline px-inset py-3">
              <span className="font-ui text-ui text-ink">{cap.heading}</span>
            </div>
            {cap.examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => onUse(ex)}
                className="flex w-full items-start gap-3 border-b border-hairline px-inset py-3 text-left last:border-b-0 hover:bg-sunken transition-colors group"
              >
                <ArrowRight size={12} strokeWidth={2} className="mt-1 shrink-0 text-ink-tertiary group-hover:text-ink transition-colors" />
                <span className="font-ui text-ui leading-5 text-ink-secondary group-hover:text-ink transition-colors">{ex}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      <div className="mt-6">
        <Link
          href="/dashboard"
          className="font-ui text-ui text-ink-secondary transition-colors hover:text-ink"
        >
          Back to directory
        </Link>
      </div>
    </section>
  );
}
