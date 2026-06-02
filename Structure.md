# CRM Agentic AI - System Structure

This document describes the architectural components, classes, services, and their interactions within the CRM Agentic AI project. It serves as a blueprint for generating UML diagrams.

## 1. High-Level Architecture

The system follows a microservices-inspired architecture:
- **Frontend**: Next.js (React) application.
- **Core API**: FastAPI hub managing data, authentication, and service orchestration.
- **AI Service**: FastAPI service interfacing with Ollama for LLM-based analysis.
- **Scraper Service**: FastAPI service using Playwright for LinkedIn scraping.
- **Database**: PostgreSQL with SQLAlchemy ORM.
- **Storage**: MinIO (S3-compatible) for storing unstructured data (e.g., email bodies).
- **LLM Engine**: Ollama running Llama models.

---

## 2. Core API (Backend Hub)

### 2.1 Models (`app/models.py`)

- `User`: Handles CRM users, roles, and verification.
- `ConnectedAccount`: Stores OAuth metadata for Google/Gmail.
- `Lead`: Central entity representing a potential customer.
- `LinkedInCredential`: Stores cookies for LinkedIn session persistence.
- `ScrapeJob`: Tracks the status and results of LinkedIn scraping tasks.
- `AgentActivity`: Log of AI-driven actions and insights for leads.
- `CopilotResult`: Stores generated sales arguments and email drafts for leads.
- `ICPBlueprint`: Defines the Ideal Customer Profile.
- `Email`: Metadata for processed emails from Gmail.

### 2.2 Routers

- `auth.py`: User registration, login (JWT), and password management.
- `google_auth.py`: OAuth2 flow for Google/Gmail.
- `leads.py`: CRUD operations for leads and trigger for `ResearchAgent`.
- `copilot.py`: Orchestrates calls to `CopilotAgent` and Gmail sending.
- `scraper.py`: Receives LinkedIn leads scraped by the browser extension (`/scraper/ext/*`), gates them against the user's active ICP, and exposes job history + AI query suggestions.
- `gmail_watcher.py`: Webhook receiver for Google Pub/Sub notifications.
- `icp.py`: Management of Ideal Customer Profile blueprints.

### 2.3 Services (`app/services/`)

- `ai_classifier.py`: Evaluates incoming emails for relevance.
- `s3_service.py`: Interfaces with MinIO for file storage.
- `eval_judge.py`: Logic for evaluating model performance.

---

## 3. AI Service

Specialized agents that interact with the Ollama API using structured JSON prompts or tool calls.

### 3.1 Agents (`agents/`)

- `ResearchAgent`:
    - **Purpose**: Analyzes lead data to produce an intent score and signals.
    - **Logic**: Uses a tier-based scoring system (0-100) based on engagement and signals.
- `CopilotAgent`:
    - **Purpose**: Generates personalized sales arguments and email drafts.
    - **Logic**: Tailors content based on the lead's intent score (HOT, WARM, COLD, LOST).
- `SearchQueryAgent`:
    - **Purpose**: Suggests 3-5 LinkedIn Sales Navigator search queries based on existing CRM leads or ICP. Uses Ollama `tool_calls` for structured output (preferred on llama3.1:8b).

---

## 4. Scraper Service

Handles the complexity of interacting with LinkedIn using browser automation.

### 4.1 Components

- `linkedin.py`: Playwright-based scraper. Features:
    - **Cookie Auth**: Uses pre-captured LinkedIn session cookies.
    - **Resilience**: Headless Chromium with custom User-Agents and random delays to avoid detection.
    - **Lead Extraction**: Targets Sales Navigator search result items using robust CSS selectors.
    - **Pagination**: Automatically navigates through requested search result pages.
- `job_runner.py`: Orchestrates a scrape job. Reports progress ("running", "completed", "failed") and streams lead batches back to `Core API`.

---

## 5. Frontend Application (Next.js)

### 5.1 Key Components (`components/`)

- `lead-pipeline.tsx`: Main dashboard showing leads grouped by status (pipeline view).
- `copilot-sidebar.tsx`: Displays AI-generated insights and email drafts for a selected lead.
- `icp-builder-form.tsx`: Interactive form for defining Ideal Customer Profiles.
- `linkedin-scraper-modal.tsx`: UI for initiating and monitoring LinkedIn scrape jobs.
- `activity-feed.tsx`: Real-time log of agent activities and system events.

### 5.2 State and Data Fetching (`hooks/` & `lib/`)

- `useAuth.ts`: Hook for managing user session and protected routes.
- `api.ts`: Centralized client for interacting with Core API.

---

## 6. Interactions and Data Flows

### 6.1 Lead Research Flow
1. **Frontend**: Calls `POST /leads/{id}/research`.
2. **Core API**: Fetches lead data from DB.
3. **Core API**: Calls `POST ai-service:8000/agent/research` with lead details.
4. **AI Service**: Prompts Ollama, parses JSON result.
5. **Core API**: Updates `Lead` (score, signals) and creates `AgentActivity`.
6. **Core API**: Returns updated Lead to Frontend.

### 6.2 Copilot Insight Flow
1. **Frontend**: Calls `GET /leads/{id}/copilot`.
2. **Core API**: Checks `CopilotResult` cache (< 24h).
3. **Core API (if cache miss)**: Calls `POST ai-service:8000/agent/copilot`.
4. **AI Service**: Generates winning argument and draft email via Ollama.
5. **Core API**: Persists result in `CopilotResult`, logs `AgentActivity`.
6. **Core API**: Returns insights to Frontend.

### 6.3 LinkedIn Scraping Flow (browser extension, BYO LinkedIn)
1. **Extension**: User opens a LinkedIn Sales Navigator search (or pastes a search URL for autonomous mode). Scraping runs in the user's own logged-in tab, so LinkedIn only sees the real browser session.
2. **Extension**: Reads the app's `access_token` cookie via `chrome.cookies` and calls `POST /scraper/ext/jobs` to create a `ScrapeJob`. Core API blocks this if the user has no active ICP.
3. **Extension**: Extracts leads per page (name, role, company, location, profile + company URL) and streams batches to `POST /scraper/ext/jobs/{id}/leads`.
4. **Core API**: Dedupes, then gates each lead against the active ICP via `POST ai-service/agent/icp-match` — matches become `status="new"` and trigger research; non-matches are saved as `status="rejected_icp"`.
5. **Core API (research)**: For matched leads, fetches the company website text and feeds it to `ResearchAgent` for intent scoring.
6. **Extension**: Finalizes the job via `PATCH /scraper/ext/jobs/{id}` and reports matched/rejected counts.

### 6.4 Gmail Integration Flow
1. **Google Pub/Sub**: Sends push notification to `core-api/gmail/webhook`.
2. **Core API**: Validates notification, triggers background task.
3. **Core API**: Calls Gmail API `history.list` to find new messages.
4. **Core API**: Calls `ai_classifier` to check if email is "worth saving".
5. **Core API**: If relevant, saves body to MinIO and metadata to `Email` table.

---

## 7. Monitoring and Observability

The system includes a dedicated monitoring stack defined in `docker-compose.yml`:
- **Grafana**: Dashboard for visualizing system health and logs.
- **Loki**: Log aggregation system.
- **Promtail**: Agent that ships container logs to Loki.
- **Ollama Health**: Direct health checks on the LLM engine.

---

## 8. UML Blueprint Summary

### 6.1 Class Diagram Entities
- `User`, `Lead`, `ConnectedAccount`, `ScrapeJob`, `AgentActivity`, `CopilotResult`, `Email`.
- `AIClient` (httpx), `S3Client` (boto3), `GmailClient` (google-api).

### 6.2 Sequence Diagram Subjects
- `Browser/User`, `FrontendApp`, `CoreAPI`, `AIService`, `ScraperService`, `Ollama`, `PostgreSQL`, `MinIO`.
