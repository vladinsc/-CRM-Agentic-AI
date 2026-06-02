# AI Tools Usage Report — CRM Agentic AI

## Overview

This document describes the AI tools used throughout the development of the CRM Agentic AI project, covering all stages from design to implementation and testing.

---

## Tools Used

### 1. Claude Code (Anthropic) — Primary Development Tool

Used as the main AI pair-programmer throughout the project via the Claude Code CLI.

**Evidence in repository:** Multiple commits carry `Co-Authored-By: Claude Sonnet 4.6` and `Co-Authored-By: Claude Opus 4.8` signatures.

**How it was used:**

- **Backend architecture** — designing the multi-service architecture (core-api, ai-service, scraper-service), FastAPI routers, SQLAlchemy models, Alembic migrations
- **AI agent implementation** — LeadResearchAgent, CopilotAgent, SearchQueryAgent, and EmailClassifier were written with Claude Code assistance, including prompt engineering and Ollama tool-calling patterns
- **CI/CD pipeline** — the full GitHub Actions workflow (lint → test → build → GHCR publish) was built with Claude Code, including fixing ruff lint enforcement and pytest configuration
- **Bug fixes** — scraper bot-detection hardening (PR #11), Ollama lock race conditions, CI environment failures
- **Test generation** — unit tests for leads endpoints and evaluation datasets for AI agents (`golden_dataset.json`)
- **Code review & refactoring** — removing unused imports, fixing SQLAlchemy ORM patterns, structlog integration

**Example commits:**
```
fix: CI failures — optional mail settings + intent_score in copilot prompt
wip(scraper): persistent Firefox profile + stealth + xvfb headful
ci: add scraper-service to GHCR publish job
```

---

### 2. v0.dev (Vercel) — Frontend Scaffolding

Used to generate the initial Next.js frontend structure and UI components.

**Evidence in repository:** Two commits authored by `v0`:
- `Initial commit from v0` — base Next.js app with shadcn/ui component setup
- `Add README.md`

**How it was used:**

- Generated the initial page layout, component structure, and Tailwind CSS configuration
- Provided the base design system (shadcn/ui components: Button, Card, Dialog, etc.)
- The generated scaffold was then extended manually and with Claude Code for all feature-specific components (LeadPipeline, CopilotSidebar, LinkedInScraperModal, etc.)

---

### 3. Jira AI — Backlog & User Stories

Used to assist in creating and organizing the project backlog.

**How it was used:**

- Generating structured user stories from feature descriptions
- Organizing epics and tasks in the Jira board (70+ issues across 12 epics)
- Suggesting task breakdowns for complex features (e.g., LinkedIn scraper pipeline split into 5 sub-tasks)

---

## Summary by Development Stage

| Stage | Tool | Usage |
|---|---|---|
| UI scaffolding | v0.dev | Initial Next.js + shadcn/ui structure |
| Backlog & planning | Jira AI | User stories, epics, task breakdown |
| Backend development | Claude Code | FastAPI routers, models, business logic |
| AI agent implementation | Claude Code | LeadResearchAgent, CopilotAgent, SearchQueryAgent, EmailClassifier |
| CI/CD pipeline | Claude Code | GitHub Actions, Docker, GHCR publish |
| Bug fixes | Claude Code | Scraper hardening, race conditions, CI env issues |
| Testing & evals | Claude Code | Unit tests, golden dataset, eval harness |
| Code review | Claude Code | Lint fixes, refactoring, noqa annotations |

---

## AI in the Product Itself

Beyond development tooling, AI is also a core part of the product:

- **LeadResearchAgent** — Ollama (llama3.2:3b) enriches lead profiles with signals and intent scores
- **CopilotAgent** — Ollama (llama3.2:3b) generates winning arguments and draft emails per lead
- **SearchQueryAgent** — Ollama (llama3.1:8b) with tool calling suggests LinkedIn search queries
- **EmailClassifier** — Ollama (llama3.2:3b) classifies incoming Gmail messages as B2B leads or noise
- **LLM-as-a-Judge** — Ollama (llama3.1:8b) evaluates 5% of production classifications for drift monitoring
