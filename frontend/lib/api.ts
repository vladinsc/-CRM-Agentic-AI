const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }))
    throw new Error(err.detail ?? "Request failed")
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T
  }
  return res.json()
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface LeadAPI {
  id: number
  name: string
  company: string
  role: string
  email: string
  phone: string | null
  deal_value: string | null
  currency: string
  deal_value_display: string | null
  intent_score: number | null
  score: number | null
  last_researched_at: string | null
  last_activity_description: string | null
  signals: string[]
  assigned_to: number | null
  status: string
  created_at: string
}

export interface ActivityAPI {
  id: number
  type: string
  message: string
  leadName: string
  timestamp: string
  status: string
}

export interface StatsAPI {
  hot_leads: number
  ai_actions_today: number
  pipeline_value: string
  pipeline_value_raw: number
}

export interface CopilotAPI {
  winning_argument: string
  draft_message: string
  confidence: number
  generated_at: string
  is_cached: boolean
}

export interface ScrapeJobAPI {
  id: number
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  query: string
  pages_requested: number
  scraped_count: number
  leads_created: number
  error_message: string | null
}

export interface SearchQuerySuggestion {
  query: string
  expected_title: string
  reasoning: string
}

interface SearchQueryResponse {
  queries: SearchQuerySuggestion[]
}

// ── API client ────────────────────────────────────────────────────────────────

export const api = {
  register: (email: string, full_name: string, password: string) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, full_name, password }) }),

  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  logout: () => request("/auth/logout", { method: "POST" }),

  me: () => request<{ id: number; email: string; full_name: string; role: string }>("/auth/me"),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),

  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }),

  // ── Leads ──────────────────────────────────────────────────────────────────
  getLeads: () => request<LeadAPI[]>("/leads"),

  createLead: (body: Omit<LeadAPI, "id" | "intent_score" | "score" | "last_researched_at" | "signals" | "assigned_to" | "created_at" | "deal_value_display">) =>
    request<LeadAPI>("/leads", { method: "POST", body: JSON.stringify(body) }),

  researchLead: (leadId: number) =>
    request<LeadAPI>(`/leads/${leadId}/research`, { method: "POST" }),

  // ── Activity ───────────────────────────────────────────────────────────────
  getActivity: (limit = 10) =>
    request<ActivityAPI[]>(`/activity?limit=${limit}`),

  // ── Stats ──────────────────────────────────────────────────────────────────
  getStats: () => request<StatsAPI>("/stats"),

  // ── Copilot ────────────────────────────────────────────────────────────────
  getCopilot: (leadId: number) =>
    request<CopilotAPI>(`/leads/${leadId}/copilot`),

  regenerateCopilot: (leadId: number) =>
    request<CopilotAPI>(`/leads/${leadId}/copilot/regenerate`, { method: "POST" }),

  sendCopilotEmail: (leadId: number) =>
    request<{ message: string; to: string }>(`/leads/${leadId}/copilot/send-email`, { method: "POST" }),
  // ── LinkedIn Scraper (browser-extension based) ───────────────────────────────
  // Scrape jobs are created/ingested by the browser extension via /scraper/ext/*.
  // These read-only endpoints expose job history to the web app.
  getScrapeJob: (jobId: number) =>
    request<ScrapeJobAPI>(`/scraper/jobs/${jobId}`),

  listScrapeJobs: () =>
    request<ScrapeJobAPI[]>("/scraper/jobs"),

  cancelScrapeJob: (jobId: number) =>
    request<{ ok: boolean; status: string }>(`/scraper/ext/jobs/${jobId}/cancel`, {
      method: "POST",
    }),

  suggestSearchQueries: () =>
    request<SearchQueryResponse>("/scraper/suggest-queries", { method: "POST" }),

  request: request,
}
