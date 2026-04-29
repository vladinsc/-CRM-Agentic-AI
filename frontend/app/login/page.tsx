"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Cpu, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useEffect } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shaking, setShaking] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(() => router.replace("/"))
      .catch(() => {});
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = (await api.login(email, password)) as { access_token: string };
      try {
        localStorage.setItem("token", data.access_token);
      } catch {}
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
      setShaking(true);
      setTimeout(() => setShaking(false), 500);
    } finally {
      setLoading(false);
    }
  }

  const inputClass = cn(
    "w-full rounded-md border bg-input px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-colors",
    error ? "border-destructive focus:ring-destructive/50" : "border-border",
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-8 rounded-xl border border-border bg-card shadow-lg">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
            <Cpu className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground">
              Agentic Command Center
            </h1>
            <p className="text-xs text-muted-foreground">
              Sign in to your account
            </p>
          </div>
        </div>

        <div className="h-px bg-border" />

        <form
          onSubmit={handleSubmit}
          className={`space-y-4 ${shaking ? "shake" : ""}`}
        >
          <div className="space-y-1.5">
            <label
              className="text-xs font-medium text-muted-foreground uppercase tracking-wide"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setError("");
              }}
              className={inputClass}
              placeholder="you@company.com"
            />
          </div>

          <div className="space-y-1.5">
            <label
              className="text-xs font-medium text-muted-foreground uppercase tracking-wide"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError("");
              }}
              className={inputClass}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
              <AlertCircle className="size-4 text-destructive shrink-0" />
              <p className="text-xs text-destructive">{error}</p>
            </div>
          )}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="size-4 rounded-full border-2 border-primary-foreground border-t-transparent animate-spin" />
                Signing in…
              </span>
            ) : (
              "Sign in"
            )}
          </Button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          No account?{" "}
          <Link
            href="/register"
            className="text-primary hover:text-primary/80 transition-colors"
          >
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
