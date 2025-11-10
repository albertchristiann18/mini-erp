# 🧾 mini-ERP — Inventory & FIFO COGS Backend

A simple **backend project** that tracks stock and calculates **COGS using FIFO**.  
Built with **Django**, **PostgreSQL**, and **uv** (fast Python environment manager).  
Designed for clean setup and easy onboarding for new contributors.

---

## 🧰 Prerequisites

Make sure these are installed before you start:

| Tool | Purpose | Link |
|------|----------|------|
| **Git** | Clone the repository | [git-scm.com](https://git-scm.com/) |
| **Docker Desktop** | Database container (PostgreSQL) | [docker.com](https://www.docker.com/products/docker-desktop) |
| **uv** | Python dependency & environment manager | [uv (Astral)](https://github.com/astral-sh/uv) |
| **VS Code** *(recommended)* | Editor with Python/Django extensions | [code.visualstudio.com](https://code.visualstudio.com/) |

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the project
```bash
git clone https://github.com/<your-username>/mini-erp.git
cd mini-erp
````

---

### 2️⃣ Start PostgreSQL (via Docker)

Run this to start your local database container:

```bash
docker compose up -d
```

This command will:

* Pull the official **PostgreSQL 16** image (if not already downloaded)
* Start a container named `mini-erp-db`
* Expose PostgreSQL on port **5433**

You can verify it's running:

```bash
docker ps
```

---

### 3️⃣ Create your environment file

Copy the example `.env.example` and rename it to `.env`:

```bash
cp .env.example .env
```

This file contains your environment variables.
By default, it looks like this:

```
DJANGO_SETTINGS_MODULE='core.settings'
SECRET_KEY=dev-change-me
DEBUG=true
ALLOWED_HOSTS=127.0.0.1,localhost
PGHOST=localhost
PGPORT=5433
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=mini_erp
```

You can adjust the values if needed.

---

### 4️⃣ Set up dependencies with uv

Install all Python dependencies and create the `.venv` automatically:

```bash
uv sync
```

This will:

* Create a local virtual environment (`.venv/`)
* Install Django, psycopg, django-environ, ruff, mypy, pytest, etc.
* Ensure your project environment is fully reproducible

If you add a new package later, use:

```bash
uv add <package-name>
```

Example:

```bash
uv add djangorestframework
```

---

### 5️⃣ Apply database migrations

Run Django migrations to initialize your database schema:

```bash
uv run python manage.py migrate
```

Then create an admin user for the Django admin panel:

```bash
uv run python manage.py createsuperuser
```

---

### 6️⃣ Run the development server

Now you can start the backend:

```bash
uv run python manage.py runserver
```

The app will start at:
👉 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

You can log in to the admin panel at:
👉 [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

Use the superuser credentials you just created.

---
### 7️⃣ Run tests

To verify everything works correctly:

```bash
uv run pytest -q
```

You can also run a specific test file:

```bash
uv run pytest inventory/tests/test_fifo.py -v
```

If all tests pass — your setup is complete 🎉

