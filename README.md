# CRM Agentic AI

Un CRM cu agenți AI care analizează lead-uri în timp real, calculează scorul de intenție și generează sugestii personalizate pentru vânzători.

Interfața are 3 coloane:
- **Activity Feed** — activitățile agenților AI în timp real
- **Intent Pipeline** — lead-urile sortate după scorul de intenție calculat de AI
- **Co-pilot Sidebar** — winning argument + draft mesaj personalizat per lead

---

## MDS 2026 — Development Process Checklist

| # | Cerință barem | Link |
|---|---|---|
| A | **2+ agenți AI funcționali** | LeadResearchAgent, CopilotAgent, SearchQueryAgent, EmailClassifier — vezi [Funcționalități](#funcționalități) |
| B1 | **User stories (min 10) + backlog creat cu AI** | [User Stories](#user-stories) · [Jira Backlog](https://crm-agentic-ai.atlassian.net/jira/software/projects/CRM/boards/35/backlog) |
| B2 | **Diagrame UML / arhitectură** | [System Architecture Diagrams](#system-architecture-diagrams) |
| B3 | **Source control: branches, PRs, min 5 commits/student** | [Pull Requests](https://github.com/vladinsc/-CRM-Agentic-AI/pulls?q=is%3Apr+is%3Amerged) · [Commits](https://github.com/vladinsc/-CRM-Agentic-AI/commits/main) |
| B4 | **Teste automate + evals agenți** | [`core-api/tests/`](./core-api/tests) · [`ai-service/tests/`](./ai-service/tests) |
| B5 | **Bug report + rezolvare cu PR** | [Issue #16](https://github.com/vladinsc/-CRM-Agentic-AI/issues/16) · [PR #11](https://github.com/vladinsc/-CRM-Agentic-AI/pull/11) |
| B6 | **Pipeline CI/CD** | [GitHub Actions](https://github.com/vladinsc/-CRM-Agentic-AI/actions) · [`.github/workflows/ci-cd.yml`](./.github/workflows/ci-cd.yml) |
| B7 | **Raport tooluri AI în dezvoltare** | [`AI_TOOLS_REPORT.md`](./AI_TOOLS_REPORT.md) |

---

## Funcționalități

- **Autentificare completă** — register, login/logout, verificare email, forgot/reset password
- **Lead Pipeline** — adaugă, vizualizează, șterge lead-uri; import CSV; scraper LinkedIn
- **4 Agenți AI:**
  - `LeadResearchAgent` — analizează profilul unui lead, extrage semnale de cumpărare, calculează scor de intenție 0–100 (pornit automat la crearea unui lead)
  - `CopilotAgent` — generează winning argument + draft email personalizat per lead (tier-based: HOT / WARM / COLD / LOST)
  - `SearchQueryAgent` — generează query-uri de căutare LinkedIn din ICP
  - `EmailClassifier` — clasifică emailuri primite prin Gmail
- **ICP Builder** — definești profilul clientului ideal în limbaj natural; AI-ul îl folosește la ranking
- **Gmail Integration** — conectare cont Google, monitorizare inbox prin Pub/Sub
- **Settings** — profil utilizator, conturi conectate, info platformă
- **Responsive** — funcționează pe mobile, tabletă și desktop
- **CI/CD** — GitHub Actions: lint → teste → build Docker → publish GHCR

---

## Pornire rapidă

### 1. Cerințe

**Windows / macOS**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalat și pornit

**Linux**
```bash
curl -fsSL https://get.docker.com | sh
sudo apt-get install -y docker-compose-plugin
sudo systemctl start docker
sudo usermod -aG docker $USER && newgrp docker
```

### 2. Clonează repo-ul

```bash
git clone https://github.com/vladinsc/-CRM-Agentic-AI.git
cd -CRM-Agentic-AI
```

### 3. Pornește serviciile

```bash
docker compose up -d
```

> Migrațiile bazei de date rulează automat la pornire.

### 4. Descarcă modelele AI (o singură dată)

```bash
docker exec crm-ollama ollama pull llama3.2:3b   # ~2GB — Research, Copilot, Email Classifier
docker exec crm-ollama ollama pull llama3.1:8b   # ~5GB — SearchQueryAgent
```

### 5. Accesează aplicația

| Serviciu | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Core API (docs) | http://localhost:8000/docs |
| AI Service (docs) | http://localhost:8001/docs |
| MinIO Console | http://localhost:9001 |

---

## Stack

| Layer | Tehnologie |
|---|---|
| Frontend | Next.js 16 + React 19 + TypeScript + Tailwind CSS + shadcn/ui |
| Core API | FastAPI + SQLAlchemy + Alembic + PostgreSQL |
| AI Service | FastAPI + Ollama (llama3.2:3b / llama3.1:8b) |
| Scraper | FastAPI + Playwright |
| Infra | Docker Compose (8 containere) |
| CI/CD | GitHub Actions + GHCR |

---

## Comenzi utile

```bash
docker compose up --build          # rebuild și pornește tot
docker compose down                # oprește (păstrează volumele)
docker compose down -v             # oprește + șterge toate datele
docker compose logs core-api -f    # urmărește logurile unui serviciu

# Teste
cd core-api && python -m pytest tests/ -q
cd ai-service && python -m pytest tests/ -q
```

---

## User Stories

| # | User Story |
|---|---|
| 1 | As a sales rep, I want to register with my email and password so that I can access my private CRM workspace |
| 2 | As a user, I want to reset my password via email so that I can recover access to my account if I forget my credentials |
| 3 | As a sales rep, I want to import leads from a CSV file so that I can bulk-add prospects without manual entry |
| 4 | As a sales rep, I want to update a lead's status so that I can track where each prospect is in my pipeline |
| 5 | As a sales rep, I want the AI to automatically research a new lead and calculate an intent score so that I can prioritize who to contact first |
| 6 | As a sales rep, I want to see AI agent activity in an auto-updating feed so that I know what research is being done in the background |
| 7 | As a sales rep, I want the AI to generate a personalized draft email for each lead so that I can send outreach without writing from scratch |
| 8 | As a sales rep, I want to send the AI-drafted email directly from the CRM so that I don't have to switch to Gmail manually |
| 9 | As a sales manager, I want to define my Ideal Customer Profile in plain language so that I have a clear reference of who my ideal customer is |
| 10 | As a sales rep, I want to scrape LinkedIn Sales Navigator search results so that I can automatically import qualified prospects into my CRM |
| 11 | As a sales rep, I want to use the Chrome extension to scrape LinkedIn leads from my own browser so that I don't need to share my LinkedIn credentials with the server |
| 12 | As a sales rep, I want the AI to suggest LinkedIn search queries based on my existing leads so that I can find similar high-intent prospects faster |
| 13 | As a sales rep, I want incoming emails to be automatically classified as leads or noise so that I don't miss potential business opportunities in my inbox |
| 14 | As a developer, I want every pull request to run automated tests and lint checks so that broken code is caught before it reaches production |
| 15 | As a user, I want to connect my Google account to the CRM and monitor my Gmail inbox so that I can receive and classify leads without leaving the platform |

---

## System Architecture Diagrams

### 1. High-Level Architecture
```mermaid
graph TD
    UI[Frontend: Next.js] --> API[Core API: FastAPI]
    API --> AI[AI Service: FastAPI]
    API --> Scraper[Scraper Service: FastAPI]
    
    API --> DB[(PostgreSQL)]
    API --> Storage[(MinIO)]
    
    AI --> Ollama[Ollama LLM]
    Scraper --> LinkedIn[LinkedIn]
    
    PubSub[Google Pub/Sub] --> API
    API --> Gmail[Gmail API]
```

### 2. CI/CD Pipeline
```mermaid
graph TD
    Start([Push / PR to main]) --> Lint[Code Quality: Ruff]
    
    Lint --> TestCore[Test Core API]
    Lint --> TestAI[Test AI Service]
    Lint --> TestFE[Build Check Frontend]

    TestCore --> BuildCheck{On main branch?}
    TestAI --> BuildCheck
    TestFE --> BuildCheck

    BuildCheck -- Yes --> Push[Publish to GHCR]
    BuildCheck -- No --> End([End Pipeline])

    subgraph "GHCR Images"
        Push --> ImageFE[crm-frontend]
        Push --> ImageCore[crm-core-api]
        Push --> ImageAI[crm-ai-service]
        Push --> ImageScraper[crm-scraper]
    end
```

### 3. Class Diagram (Data Models)
```mermaid
classDiagram
    class User {
        +UUID id
        +String email
        +String role
    }
    
    class ConnectedAccount {
        +UUID id
        +UUID user_id
        +String provider
    }

    class Lead {
        +UUID id
        +String name
        +Integer intent_score
        +String status
    }

    class ScrapeJob {
        +UUID id
        +String query
        +String status
    }

    class AgentActivity {
        +UUID id
        +UUID lead_id
        +String action
    }

    class CopilotResult {
        +UUID id
        +UUID lead_id
        +Text sales_argument
    }

    class Email {
        +UUID id
        +String message_id
        +Boolean is_worth_saving
    }
    
    class ICPBlueprint {
        +UUID id
        +JSON criteria
    }

    User *-- ConnectedAccount
    User *-- Lead
    ScrapeJob *-- Lead
    Lead *-- AgentActivity
    Lead *-- CopilotResult
    Lead *-- Email
```

### 3. User Flow — Main Journey
```mermaid
flowchart TD
    A([Start]) --> B[Register / Login]
    B --> C{How to add leads?}

    C -->|Manual| D[Fill lead form]
    C -->|Bulk| E[Import CSV]
    C -->|LinkedIn| F[LinkedIn Scraper\ndefine search query]

    D --> G[Lead created in pipeline]
    E --> G
    F --> G

    G --> H[LeadResearchAgent runs automatically\nextract signals · score intent 0–100]
    H --> I[Intent Pipeline updated\nlead ranked by score]

    I --> J[Sales rep selects a lead]
    J --> K[CopilotAgent generates\nwinning argument + draft email]
    K --> L{Action}

    L -->|Send email| M[Email sent via Gmail]
    L -->|Adjust & send| N[Edit draft → send]
    L -->|Skip| O[Move to next lead]

    M --> P([Done])
    N --> P
    O --> J
```

### 4. User Flow — Gmail Email Classification
```mermaid
flowchart TD
    A([New email arrives in Gmail]) --> B[Google Pub/Sub sends webhook\nto Core API]
    B --> C[Core API fetches email via Gmail API]
    C --> D[EmailClassifier agent evaluates\nis this a B2B lead or noise?]
    D --> E{is_worth_saving?}
    E -->|Yes| F[Store body in MinIO\nSave metadata in PostgreSQL]
    E -->|No| G[Discard — no action]
    F --> H[Email visible in CRM inbox]
    H --> I([Sales rep reviews lead])
```

### 6. Lead Research Flow (Technical)
```mermaid
sequenceDiagram
    participant UI as Frontend
    participant Core as Core API
    participant DB as PostgreSQL
    participant AI as AI Service
    participant LLM as Ollama

    UI->>Core: POST /leads/{id}/research
    Core->>DB: Fetch Lead Data
    DB-->>Core: Lead Record
    Core->>AI: POST /agent/research
    
    Note right of AI: ResearchAgent execution
    AI->>LLM: Prompt Evaluation
    LLM-->>AI: JSON Result
    
    AI-->>Core: Parsed Insights
    Core->>DB: Update Lead
    Core->>DB: Create AgentActivity
    Core-->>UI: 200 OK
```

### 7. LinkedIn Scraping Flow (Technical)
```mermaid
sequenceDiagram
    participant UI as Frontend
    participant Core as Core API
    participant DB as PostgreSQL
    participant Scraper as Scraper Service
    participant LI as LinkedIn

    UI->>Core: POST /scraper/jobs
    Core->>DB: Create ScrapeJob
    Core->>Scraper: POST /jobs (async)
    Core-->>UI: 202 Accepted
    
    Scraper->>LI: Scrape Data
    
    loop Every Page
        LI-->>Scraper: HTML Data
        Scraper->>Core: POST /leads (Batch)
        Core->>DB: Save Leads
    end
    
    Scraper->>Core: PATCH /jobs (completed)
    Core->>DB: Update Status
```

### 8. Gmail Integration Flow (Technical)
```mermaid
sequenceDiagram
    participant PubSub as Google Pub/Sub
    participant Core as Core API
    participant Gmail as Gmail API
    participant AI as AI Classifier
    participant MinIO as MinIO Storage
    participant DB as PostgreSQL

    PubSub->>Core: POST /gmail/webhook
    Core-->>PubSub: 200 OK
    
    Core->>Gmail: Fetch new messages
    Gmail-->>Core: Raw Email
    
    Core->>AI: evaluate_relevance()
    AI-->>Core: is_worth_saving
    
    alt is_worth_saving == True
        Core->>MinIO: Store Body
        Core->>DB: Save Metadata
    end
```
