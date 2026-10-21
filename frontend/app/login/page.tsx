"use client";

import { ArrowRight, KeyRound, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Logo } from "@/components/ui/Logo";
import { Caption, PanelTitle } from "@/components/ui/Panel";
import { login } from "@/lib/api";

const DEMO_ACCOUNTS = [
  { role: "System Admin",       email: "admin@health.demo",       password: "admin123",  note: "Full access" },
  { role: "Department Head",    email: "head@health.demo",        password: "dept123",   note: "View + create" },
  { role: "Staff Coordinator",  email: "coordinator@health.demo", password: "coord123",  note: "View + create" },
  { role: "Compliance Officer", email: "compliance@health.demo",  password: "comply123", note: "View + audit + revoke" },
];

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await login(email, password);
      localStorage.setItem("gatekeep_token", response.access_token);
      localStorage.setItem("gatekeep_user", JSON.stringify(response.user));
      router.push("/dashboard");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to log in");
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(account: (typeof DEMO_ACCOUNTS)[number]) {
    setEmail(account.email);
    setPassword(account.password);
    setError("");
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="border-b border-hairline bg-surface">
        <div className="mx-auto flex max-w-7xl items-center px-6 py-4">
          <Link href="/" className="text-brand">
            <Logo size={22} />
          </Link>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center p-6">
        <div className="flex w-full max-w-[680px] flex-col gap-6 lg:flex-row lg:items-start">
          {/* Login form */}
          <form
            onSubmit={handleSubmit}
            className="flex w-full flex-col gap-6 bg-surface p-inset lg:w-[325px] lg:shrink-0"
          >
            <PanelTitle>Clinical Access Login</PanelTitle>

            <Field
              icon={Mail}
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />

            <Field
              icon={KeyRound}
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            <Button
              type="submit"
              icon={ArrowRight}
              disabled={loading || !email || !password}
              className="w-full justify-start"
            >
              {loading ? "Signing in" : "Login"}
            </Button>

            {error ? (
              <Caption className="text-ink">{error}</Caption>
            ) : null}
          </form>

          {/* Demo accounts panel */}
          <div className="flex-1 bg-surface p-inset">
            <PanelTitle>Demo accounts</PanelTitle>

            <Caption className="mt-2 text-ink-tertiary">
              Click any role to prefill credentials.
            </Caption>

            <div className="mt-4">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => fillDemo(account)}
                  className="flex w-full flex-col gap-1 border-b border-hairline px-inset py-3 text-left transition-colors last:border-b-0 hover:bg-sunken"
                >
                  <span className="flex items-baseline justify-between gap-4">
                    <span className="font-ui text-ui text-ink">{account.role}</span>
                    <span className="font-ui text-ui text-ink-tertiary">{account.note}</span>
                  </span>
                  <span className="font-ui text-ui text-ink-tertiary">{account.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
