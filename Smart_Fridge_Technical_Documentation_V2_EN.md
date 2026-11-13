# Technical Documentation — Smart Fridge & Nutrition Coach

> **Target audience:** beginner/intermediate Python developers, a teammate taking over the project, and instructors assessing its architecture.  
> **Purpose:** install, understand, troubleshoot, and extend the application without having to guess where to make changes.  
> **Reference:** `Theo_L_Maxime_Projet_Smart_FridgeNEWDB(20261008-121939).zip`, inspected on October 8, 2026.  
> **Verification scope:** static code review; remote services and actual production behavior were not executed during this review.

## 1. Overview and scope

Smart Fridge is a web application for food inventory management and nutritional tracking. It provides a refrigerator inventory, expiration alerts, recipes, food consumption records, meal planning, notifications, and an administration interface.

**What this documentation enables:** start the application, locate components, understand data flows, test a user journey, and identify technical limitations.

**Reading prerequisites:** basic familiarity with Python, HTTP (GET/POST), SQL, virtual environments, and environment variables. Beginners can follow the commands in Section 4.

## 2. Architecture and interactions

```mermaid
flowchart TD
    U[User / browser] --> F[FastAPI HTML pages]
    F --> R[Routes and business logic]
    R --> ORM[SQLAlchemy]
    ORM --> DB[(Supabase PostgreSQL or SQLite)]
    R --> M[TheMealDB - recipes]
    R --> USDA[USDA FoodData Central - nutrition]
    R --> T[Translation service]
    A[JSON API /docs] --> R
```

- **Server:** FastAPI, started from `main.py`.
- **Interface:** server-rendered HTML through `app/web/layout.py` and `app/web/pages/`, with styles in `static/`.
- **API:** account-related routes in `app/routers/`; OpenAPI documentation at `/docs` while the server is running.
- **Persistence:** SQLAlchemy models in `app/db/models.py`; connection and sessions in `app/db/database.py`.
- **External services:** TheMealDB and USDA through `app/web/data.py` and other page functions; translations and application-side caches.

### Useful project tree

```text
main.py                         # FastAPI initialization, routers, middleware, errors
app/
  core/                         # Security, JWT, dependencies, metabolic calculations
  db/database.py                # DATABASE_URL, engine, sessions, schema adjustments
  db/models.py                  # SQLAlchemy models and tables
  routers/auth.py               # Registration, login, account API
  routers/profile.py            # Profile API
  web/layout.py                 # Page rendering and authentication middleware
  web/data.py                   # External data requests
  web/pages/
    home.py                     # Home
    fridge.py                   # Inventory, recipes, consumption, leftovers
    nutrition.py                # Nutritional summary
    planner.py                  # Meal planning
    notifications.py            # Notifications
    alerts.py                   # Alerts
    admin.py                    # Administration
    profile.py                  # User profile
static/                          # CSS and other static assets
create_admin.py                 # Administrator creation
migrate_sqlite_to_supabase.py   # Data migration
 test_supabase_connection.py    # PostgreSQL connection check
requirements-supabase.txt       # Additional PostgreSQL/translation dependencies
README.md                       # Repository overview and instructions
```

**Important:** `app/web/routes.py` exists, but pages are registered individually from `main.py`. To change an active route, start with the imports and `include_router` calls in `main.py`, not merely a filename.

## 3. Configuration and database

### Settings

| Setting | Location | Purpose | How to verify |
|---|---|---|---|
| `DATABASE_URL` | Root `.env` | PostgreSQL connection; if missing, falls back to SQLite `sqlite:///./smartfridge.db` | Connection script, then startup |
| `USDA_API_KEY` | Environment variable | USDA requests | Catalog/nutrition results |
| JWT settings | `app/core/jwt.py` and related configuration | Issue and validate tokens | Test login and a protected route |

Never commit `.env`, passwords, or API keys to Git. Do not copy someone else's credentials.

### Tables identified in `app/db/models.py`

| Table | Purpose |
|---|---|
| `users` | Accounts, profiles, and administrator role |
| `fridge_items` | Products, quantities, categories, and expiration dates |
| `app_dates` | Per-user simulated date |
| `daily_logs` | Daily history and snapshots |
| `recipe_translations` | Stored recipe translations |
| `nutrition_intakes` | Recorded nutritional consumption |
| `recipe_leftovers` | Recipe leftovers |
| `meal_plans` | Scheduled meals |
| `recipe_nutrition_cache` | Cached estimated nutritional values |
| `notifications` | Notifications and read status |
| `admin_logs` | Administrative action history |

Table names come from model declarations. For exact columns and constraints, consult `app/db/models.py`; do not assume undeclared foreign keys.

**Schema creation:** `main.py` calls `Base.metadata.create_all(bind=engine)` at startup. This creates missing tables but **does not automatically migrate every column in existing tables**. `app/db/database.py` contains targeted column adjustments (`ensure_fridge_user_id_column`, `ensure_user_profile_columns`). Any other structural change requires a verified migration and a prior backup.

## 4. Installing and running the project (Windows PowerShell)

### Prerequisites

- Python installed and available through `python`.
- Access to a Supabase PostgreSQL database **or** deliberate use of the SQLite fallback.
- Internet access for recipe/nutrition APIs.
- Project files extracted into a local folder.

### Procedure

1. Open PowerShell **in the directory containing `main.py`**.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies. The inspected archive contains `requirements-supabase.txt` but **no root `requirements.txt`**. The README command (`pip install -r requirements.txt`) therefore will not work as written for this archive. At minimum, run:

   ```powershell
   python -m pip install fastapi uvicorn sqlalchemy python-dotenv "psycopg[binary]" requests python-multipart passlib bcrypt python-jose deep-translator
   python -m pip install -r requirements-supabase.txt
   ```

   This is a **starting dependency list**, not a guaranteed version lockfile. If an import is missing, identify the corresponding package and add a version-controlled dependency manifest.

4. Create a root `.env` file using the connection string from your own Supabase project:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/postgres
   USDA_API_KEY=YOUR_KEY_IF_USED
   ```

   Adjust other necessary settings after inspecting `app/core/jwt.py` and the relevant modules. Do not use placeholder values in production.

5. Test the connection and start the server:

   ```powershell
   python test_supabase_connection.py
   uvicorn main:app --reload
   ```

6. Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/docs`.

### Expected result

- Server starts without a traceback.
- Home page loads.
- `/docs` lists the API routes.
- A test registration/login succeeds against a test database.

**If it fails:** `ModuleNotFoundError` → missing dependency; SQLAlchemy/psycopg error → check `DATABASE_URL`, network, and permissions; `Address already in use` → stop the previous server; changes not visible → check the working directory and restart Uvicorn.

## 5. Verifiable technical workflows

### 5.1 Authentication and profile

**Purpose:** create an account, sign in, and manage personal information.  
**Code:** `app/routers/auth.py`, `app/routers/profile.py`, `app/core/security.py`, `app/core/jwt.py`, `app/web/layout.py`.  
**API routes:** `POST /register`, `POST /login`, `GET /me` (subject to any prefixes defined on routers), plus profile routes.  
**Test:** create a test user, sign in, open the profile, and confirm an unauthenticated user cannot edit someone else's profile.  
**Limitation:** a Bearer scheme in OpenAPI alone does not prove every HTML page enforces the same checks; inspect actual dependencies and middleware.

### 5.2 Inventory and expiration

**Purpose:** add, view, and delete products, and detect upcoming expiration dates.  
**Code:** `app/web/pages/fridge.py`, `app/web/pages/alerts.py`, `app/db/models.py`.  
**Routes:** `GET /fridge`, `POST /fridge`, `POST /fridge/delete`, `POST /fridge/next-day`, `GET /alerts`.  
**Example:** add a test product with a near expiration date; open Inventory and Alerts; advance the simulated date and check how the alert changes.  
**Expected result:** the product appears under the correct account, and the alert reflects the simulated date.  
**Special case:** the simulated date (`app_dates`) is not necessarily the real date used by every other module; check consistency when comparing expiration and consumption.

### 5.3 Recipes, consumption, and leftovers

**Purpose:** find recipes, display preparation instructions, record a consumed portion, and manage leftovers.  
**Code:** `app/web/pages/fridge.py`, `app/web/data.py`, models `NutritionIntakeDB` and `RecipeLeftoverDB`.  
**Routes:** `GET /recipes`, `GET /recipes/{meal_id}/instructions`, `POST /recipes/consume`, `POST /recipes/leftover/consume`.  
**Example:** select a recipe, read its instructions, record 50% as consumed, then check the nutritional summary and leftovers.  
**Expected result:** only the declared portion is added to actual intake; the remainder can be retrieved.  
**Limitations:** recipe availability and translation depend on external services and caches; nutritional figures are estimates, not clinical measurements.

### 5.4 Meal planning

**Purpose:** save and remove planned recipes on a calendar.  
**Code:** `app/web/pages/planner.py`, `MealPlanDB`, `RecipeNutritionCacheDB`.  
**Identified routes:** `GET /planner`, `POST /planner/save`, `POST /planner/delete`.  
**Example:** choose a date and meal slot, save a recipe, reload `/planner`, verify it persists, and then delete it.  
**Expected result:** the scheduled recipe remains visible after reloading and disappears after deletion.  
**Important limitation:** in **this inspected archive**, `planner.py` contains **no** “Prepare” route or meal-consumption logic initiated from the planner. The “Plan → Prepare → Eat” functionality mentioned for other versions must **not** be described as implemented here until the corresponding files are integrated and tested.

### 5.5 Nutrition and notifications

**Purpose:** show nutritional tracking and persistent alerts.  
**Code:** `app/web/pages/nutrition.py`, `app/web/pages/notifications.py`, `app/core/metabolism.py`.  
**Routes:** `GET /nutrition`, `GET /notifications`, `POST /notifications/read`, `POST /notifications/read-all`.  
**Test:** record a consumed meal and open Nutrition; open Notifications, mark an item as read, and refresh.  
**Expected result:** consumption appears in the summary, and read/unread status remains consistent after refreshing.  
**Limitation:** verify the nutritional target rules and data sources before interpreting results.

### 5.6 Administration

**Purpose:** manage users, products, and logs.  
**Code:** `app/web/pages/admin.py`, `app/core/admin.py`, `create_admin.py`.  
**Routes:** `GET /admin`, `GET /admin/users/{user_id}`, and several `POST /admin/users/{user_id}/...` endpoints.  
**Test:** create an administrator in a test environment using `python create_admin.py`; verify a standard account cannot access administrative operations.  
**Expected result:** administrators can access authorized screens, while standard users are denied.  
**Important:** test authorization on the server, not just whether buttons are visible.

## 6. Modifying the project without breaking other modules

| Change needed | Starting files | Minimum verification |
|---|---|---|
| Add a product field | `app/db/models.py`, `app/web/pages/fridge.py` | Migration + create/read a product |
| Change an expiration rule | `app/web/pages/alerts.py`, `app/web/pages/fridge.py` | Dates D-3, D-1, today, overdue |
| Change a nutrition formula | `app/core/metabolism.py`, `app/web/pages/nutrition.py` | Test case with known values |
| Add a planner status | `app/db/models.py`, `app/web/pages/planner.py` | Persistence after restart, migration |
| Add a notification | `app/web/pages/notifications.py` and the relevant producer | Created, read, not duplicated |
| Add a route | Module under `app/web/pages/`, then `main.py` | URL responds; access checks tested |
| Change the appearance | `static/`, `app/web/layout.py` | Check desktop and mobile layouts |

### Pre-release checks

1. Back up the test database before any schema change.
2. Check Python syntax for modified files: `python -m compileall -q app main.py`.
3. Start the application and open the modified page.
4. Test a normal workflow **and** an error case (signed out, invalid input, unavailable external API).
5. Ensure no API key, password, `.env`, or `venv` directory is added to the repository.
6. Update this document whenever a route, model, setting, or limitation changes.

## 7. Troubleshooting and known limitations

| Symptom | Possible cause | Action | Expected verification |
|---|---|---|---|
| Server will not start | Missing dependency | Read the final traceback line and install the package | Startup succeeds |
| Database connection refused | Invalid `DATABASE_URL` or network access | Run the connection script; check URL and permissions | Connection succeeds |
| Table exists but column is missing | `create_all()` does not migrate existing tables | Back up, then apply a targeted migration | Column visible in PostgreSQL |
| Recipes missing or slow | TheMealDB API unavailable or slow | Check network, logs, and cache | Recipes available or error handled |
| Nutrition data missing | Missing USDA key or API unavailable | Check `USDA_API_KEY` and external response | Data displayed or clear message |
| Plan/prepare feature missing | Deployed `planner.py` version lacks integration | Check deployed routes and files | Button and workflow tested after integration |
| Changes do not appear | Old server or wrong directory | Stop Uvicorn; restart from the `main.py` directory | New behavior visible |

### Limitations and risks

- **CORS security:** `main.py` configures `allow_origins=["*"]`; restrict this to permitted origins before public exposure.
- **Schema management:** no general versioned migration mechanism was identified in the inspected startup files.
- **Dependencies:** the `requirements.txt` mentioned in the README is absent from this archive; reproducible installation is a priority improvement.
- **External data:** recipes, translations, and USDA data may be incomplete, slow, or unavailable.
- **OpenAPI documentation:** the code adds a global Bearer scheme; verify that this matches the actual route protections.
- **Archive:** it includes a `venv/` directory; this should not be treated as the source of truth for dependencies or committed to version control.

## 8. References, maintenance, and ownership

| Reference | Location | When to update |
|---|---|---|
| Startup code and routers | `main.py`, `app/routers/`, `app/web/pages/` | Route added or changed |
| Data schema | `app/db/models.py`, any migrations | Table/column changed |
| Configuration | `app/db/database.py`, secret-free `.env` example | Provider or environment variable changed |
| Installation | `README.md`, dependency manifest | Python/packages updated |
| Architecture decisions (ADRs) | `docs/adr/` directory **to be created if adopted** | Significant technical decision |
| This documentation | `docs/Documentation_Technique_Smart_Fridge_V2.md` **suggested location** | Each release changing a workflow, route, model, or limitation |

**Suggested ownership:** the developer modifying a component updates the relevant section and asks their teammate to review it before merging or delivery. This is a **recommendation**, not a rule verified in the repository.

**Validity criteria:** installation commands work on a clean machine; Section 5 scenarios pass; Section 7 limitations are reassessed; cited paths match the delivered version.

## 9. Self-assessment against the six required criteria

| Criterion | How this documentation addresses it |
|---|---|
| **Audience-appropriate** | Audience and prerequisites are stated up front |
| **Useful** | Concrete tasks: install, test, troubleshoot, modify |
| **Accurate** | Code and routes tied to an identified archive; limitations and missing features disclosed |
| **Actionable** | Commands, files to edit, and step-by-step procedures |
| **Verifiable** | Expected outcomes for each workflow and common issue |
| **Maintainable** | Sources of truth, update triggers, and suggested ownership |

---

*This document describes the inspected version and distinguishes behavior visible in source code from operations requiring runtime testing. Review it after each significant project change.*
