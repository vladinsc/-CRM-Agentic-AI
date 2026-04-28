# db/

Reserved for complex SQL queries and repository pattern implementations.

Will be populated in EPIC 6+ as query complexity grows (JOINs, pagination, aggregations).

## Current models
- `User` — authentication, roles
- `Lead` — pipeline, intent score, signals (JSONB)
- `AgentActivity` — AI agent action log

## Planned
- Query objects for lead scoring analytics
- Aggregation queries for dashboard stats
- Paginated lead search with filters
