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
| **Docker Desktop** | Container runtime & Database container | [docker.com](https://www.docker.com/products/docker-desktop) |
| **uv** | Python dependency & environment manager | [uv (Astral)](https://github.com/astral-sh/uv) |
| **VS Code** *(recommended)* | Editor with Python/Django extensions | [code.visualstudio.com](https://code.visualstudio.com/) |
| **Minikube** | Local Kubernetes environment | [minikube.sigs.k8s.io](https://minikube.sigs.k8s.io/docs/start/) |
| **kubectl** | Command line tool for Kubernetes | [kubernetes.io/docs/reference/kubectl/](https://kubernetes.io/docs/reference/kubectl/) |
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


## 🚀 Deployment (Minikube / Kubernetes Test)

This section details how to deploy the application into a local Kubernetes cluster (Minikube) using pre-built manifests and the included deployment script.

### 1️⃣ Ensure Minikube is Running

Before proceeding, make sure Minikube is started:

```bash
minikube start
```

### 2️⃣ Grant Execute Permission to the Deployment Script

The `local_deploy.sh` script handles building the Docker image, setting the Minikube context, creating the Kubernetes Secret, and deploying all services.

```bash
chmod +x local_deploy.sh
```

### 3️⃣ Run the Kubernetes Deployment

This single script command performs the entire build and deployment process:

```bash
./local_deploy.sh
```

**What this script does:**

1.  Sets your local Docker client to build inside the Minikube VM's image registry.
2.  Builds the optimized multi-stage Docker image (`mini-erp-uv:v1`).
3.  Creates a Kubernetes Secret (`mini-erp-db-secret`) from your `.env` file.
4.  Deploys the PostgreSQL database (via `k8s/postgres.yaml`).
5.  Deploys the Django application (via `k8s/django-app.yaml`).
      * **Crucially:** The application container runs the `entrypoint-k8s.sh` script, which automatically **waits for the database**, **runs migrations**, **creates the superuser**, and **starts the Gunicorn server**.

### 4️⃣ Access the Application

Once the script finishes, it will provide the final access URL. If you need to retrieve it manually:

```bash
minikube service django-app-service --url
```

-----
