# Smart Fridge — Architecture Decision Records (ADR)

## ADR-001 — Python and FastAPI Backend

### Specific context
The project must provide web workflows and server-side processing for accounts, fridge inventory, recipes, and nutritional tracking.

### Realistic options
- **Selected option:** Keep Python and FastAPI as the HTTP backend, separating routes, business logic, and data access.
- **Other options:** Flask; Django; JavaScript/Node.js backend.

### Decision and rationale
Python allows business logic to be shared across modules; FastAPI provides explicit routing and dependencies. This choice matches the observed project structure.

### Benefits and limitations
- **Benefits:** Shared Python business logic, explicit routing and dependency management, and alignment with the existing codebase.
- **Limitations / risks:** Keep web logic modular; add route tests, input validation, and endpoint documentation.

### Reconsideration conditions
If the backend needs to expose a public API, handle significantly higher traffic, or route maintenance becomes excessively costly.

### Practical verification
Start the server and check that login, fridge, and planning routes respond; run any available route tests.

### Reference code
`app/web/routes.py` · `main.py` · `app/routers/auth.py`

---

## ADR-002 — Supabase PostgreSQL for Data Persistence

### Specific context
User and meal data must persist across sessions and be accessible to developers working from multiple computers.

### Realistic options
- **Selected option:** Use PostgreSQL hosted by Supabase, with a connection URL supplied through configuration.
- **Other options:** Local SQLite; self-hosted PostgreSQL; MySQL.

### Decision and rationale
A remote database facilitates collaboration and provides PostgreSQL's relational capabilities. The migration script indicates a transition from SQLite.

### Benefits and limitations
- **Benefits:** Shared remote access and relational database features.
- **Limitations / risks:** Dependency on network connectivity and the remote service; secure credentials, back up data, and manage schema changes through migrations.

### Reconsideration conditions
If Supabase costs, offline requirements, data residency, or connection limits change.

### Practical verification
Check the connection using local configuration, then confirm that a test record remains available after restarting the application.

### Reference code
`app/db/database.py` · `app/db/models.py` · `migrate_sqlite_to_supabase.py`

---

## ADR-003 — SQLAlchemy for Models and SQL Access

### Specific context
The system manages related entities: users, inventory, food intake, meal planning, and notifications.

### Realistic options
- **Selected option:** Represent tables with SQLAlchemy models and access the database through sessions.
- **Other options:** Handwritten SQL; another ORM; direct PostgreSQL driver access.

### Decision and rationale
Models centralize the data structure and relationships, while queries remain integrated into Python code.

### Benefits and limitations
- **Benefits:** Centralized data models and Python-integrated queries.
- **Limitations / risks:** Use explicit transactions, close sessions, monitor queries, and use a migration tool when modifying existing tables.

### Reconsideration conditions
If schema changes become frequent, query performance degrades, or another storage model is introduced.

### Practical verification
Create and retrieve a test record; check session cleanup and migrations when changing a table.

### Reference code
`app/db/models.py` · `app/db/database.py`

---

## ADR-004 — TheMealDB External API for Recipes

### Specific context
The application must suggest meals without manually maintaining a comprehensive recipe catalog.

### Realistic options
- **Selected option:** Fetch recipes from an external service, then format and enrich them within the application.
- **Other options:** Local catalog; manual entry; another recipe provider.

### Decision and rationale
An external catalog speeds up recipe availability; French-language adaptations and nutritional estimates are handled by application code.

### Benefits and limitations
- **Benefits:** Faster access to a broad recipe catalog.
- **Limitations / risks:** Handle network failures, request limits, and inconsistent data; provide fallbacks and distinguish nutritional estimates from guaranteed values.

### Reconsideration conditions
If TheMealDB becomes unavailable, changes its terms of use, or no longer offers enough suitable recipes.

### Practical verification
Display a known recipe and test the behavior when the external service is unavailable.

### Reference code
`app/web/data.py` · `app/web/pages/products.py` · `app/web/pages/planner.py`

---

## ADR-005 — Server-Side Authentication and Authorization

### Specific context
Fridge inventory, profiles, and nutritional records are personal; certain administrative features require separate privileges.

### Realistic options
- **Selected option:** Manage identity and access controls on the server, store hashed passwords, and use session/token mechanisms as appropriate for each route.
- **Other options:** No authentication; external identity provider; client-side-only sessions.

### Decision and rationale
Security, JWT, dependency, and administration modules exist in the project; authorization must be enforced for every sensitive operation.

### Benefits and limitations
- **Benefits:** Centralized identity and access checks aligned with existing modules.
- **Limitations / risks:** Verify session expiration, cookie attributes, CSRF protection where relevant, login-attempt limits, and per-user data isolation.

### Reconsideration conditions
If security requirements change, an incident occurs, or third-party authentication is considered.

### Practical verification
Confirm that unauthenticated users cannot access private data and that non-admin accounts cannot perform administrative operations.

### Reference code
`app/core/security.py` · `app/core/jwt.py` · `app/core/dependencies.py` · `app/core/admin.py` · `app/routers/auth.py`

---

## ADR-006 — Persistent Caching of Translations and Nutritional Data

### Specific context
External recipes may require translation and nutritional estimation; repeating these operations increases response time and dependence on third-party services.

### Realistic options
- **Selected option:** Reuse previously computed results, in memory or in the database depending on the data type.
- **Other options:** Recompute on every display; in-memory cache only; external Redis cache.

### Decision and rationale
Reusing results reduces latency and repeated requests; cache models and nutritional modules exist in the project.

### Benefits and limitations
- **Benefits:** Faster responses and fewer repeated external calls.
- **Limitations / risks:** Define cache keys, invalidation rules, and source traceability; recompute stale data when necessary.

### Reconsideration conditions
If recipes, translations, or calculations change, or cached data becomes outdated.

### Practical verification
Open the same recipe twice; check result consistency and the planned refresh behavior.

### Reference code
`app/db/models.py` · `app/web/data.py` · `app/web/nutrition_engine.py`
