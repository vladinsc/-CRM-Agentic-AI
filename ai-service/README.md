# Hybrid Lead Scoring Engine

## Overview
The Hybrid Lead Scoring Engine is a custom evaluation system designed to rank incoming CRM leads based on a user's Ideal Customer Profile (ICP). 


## Core Architecture
The final lead score (0-100) is a blended result of two distinct systems:

1. **The Rule Engine (70% weight):** A strict, database-driven calculator. It checks hard facts (e.g., Revenue > $1M, Industry = SaaS) and provides explainable, deterministic scores.
2. **The Vector Engine (30% weight):** A semantic search model (`all-MiniLM-L6-v2`). It compares the "vibe" of the lead's company description against the user's natural language ICP description using Cosine Similarity.

---

## 1. Database Schema (PostgreSQL)

To isolate scoring logic for multi-tenant users, rules are stored in the database rather than hardcoded in Python.

### `user_icp_rules` Table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | SERIAL | Primary Key |
| `user_id` | INTEGER | Foreign key to the user account |
| `criteria_field` | VARCHAR | The data field to check (e.g., 'industry', 'revenue') |
| `operator` | VARCHAR | 'equals', 'contains', 'greater_than' |
| `target_value` | VARCHAR | The desired value (e.g., 'SaaS', '1000000') |
| `point_value` | INTEGER | Points awarded if matched (e.g., 40) |

---

## 2. The Scoring Workflow

When a new lead enters the pipeline, the system executes the following steps:

1. **Data Extraction:** A background worker scrapes the lead's website and uses an LLM to extract a clean JSON object (industry, revenue, tech stack) and a short text description.
2. **Rule Evaluation:** The Python engine fetches the user's custom rules from the database and compares them against the extracted JSON. It calculates partial points for numbers that are "close" to the target.
3. **Vector Comparison:** The Python engine generates a vector embedding of the lead's description and compares it to the user's ICP vector.
4. **Final Calculation:** The system blends the scores:
   `Total Score = (Rule Score * 0.7) + (Vector Score * 0.3)`

---

## 3. Active Learning (The Feedback Loop)

The system features a continuous learning mechanism. When a user manually rates a lead in the UI (on a scale of 1 to 10), the system adjusts its internal vector representation.

* **Rating 10/10:** The system mathematically pulls the user's ICP vector *closer* to the lead's vector.
* **Rating 1/10:** The system pushes the user's ICP vector *away* from the lead's vector.

**Formula used:**
`V_new = V_icp + (learning_rate * direction * V_lead)`

This allows the AI to silently learn the user's true preferences over time without requiring them to manually update their database rules.

---

## 4. API Endpoints

* `POST /api/icp-rules` - Create a new programmatic scoring rule for a user.
* `GET /api/icp-rules` - Retrieve all current scoring rules for the authenticated user.
* `POST /api/leads/score` - Trigger a manual recalculation of a lead's score.
* `POST /api/leads/{id}/feedback` - Submit a 1-10 rating to trigger the Active Learning vector shift.