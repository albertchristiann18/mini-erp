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

## ⚙️ Setup (Development)

### 1️⃣ Create your `.env` file

Copy the example file:

```bash
cp .env.example .env
```

Your `.env` file should look similar to:

```
# Django
DJANGO_SETTINGS_MODULE=core.settings
SECRET_KEY=dev-change-me
DEBUG=true
ALLOWED_HOSTS=127.0.0.1,localhost

# Database (LOCAL Django → Docker Postgres)
DB_NAME=mini_erp
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5433

# Initial superuser (auto-created by migrate service)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=changeme123
```

---

### 2️⃣ Start PostgreSQL via Docker

```bash
docker compose up -d
```

This will:

* Start the **Postgres** container
* Run the **migrate** service
* Apply all Django migrations
* Automatically create a superuser
  (based on values inside `.env`)

You do **NOT** need to run migrations manually.

You can confirm everything ran:

```bash
docker compose logs migrate
```

---

### 3️⃣ Install Python dependencies with uv

```bash
uv sync
```

This will:

* Create a `.venv/`
* Install all project dependencies
* Make the environment ready

---

### 4️⃣ Run the backend (Django) locally

```bash
uv run python manage.py runserver
```

Backend URL:
👉 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

Admin panel:
👉 [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
(**login using the auto-created superuser from `.env`**)

---

## 🎉 Development Setup Complete

Your environment now includes:

✔ PostgreSQL running in Docker
✔ Migrations automatically applied
✔ Superuser automatically created
✔ Django running locally with uv

If you want, I can also generate a **Production README** or include sections for:

* test instructions
* API documentation
* ERD diagrams
* pre-commit setup
  Just let me know!


kubernetes run
chmod +x local_deploy.sh


./local_deploy.sh