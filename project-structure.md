# mini-erp — Project Structure

## Stack

**Django 5.2 + DRF 3.16** · **PostgreSQL 15** · **Python 3.12** · **uv** · **Docker** · **pytest** · **mypy** · **ruff**

---

## Quick Reference

| I want to... | Go to... |
|---|---|
| Add or edit a product / variant | `apps/inventory/models.py` (model), `apps/inventory/services/product_service.py` (business logic), `apps/inventory/views.py` (API) |
| Record a payment against a PO | `apps/finance/services/accounts_payable_service.py` → `record_payment()` |
| Add a new API endpoint | Create serializer in `<app>/serializers.py`, add view in `<app>/views.py`, register route in `<app>/urls.py`, then include in `core/urls.py` |
| Change a shared base model (e.g. add field to `Company`) | `core/models.py` (abstract bases in `TimeStampedModel` / `DefaultModel`) |
| Run tests | `uv run pytest` (or `uv run pytest apps/<app>/tests.py -k <test_name>`) |
| Understand how data flows end-to-end | See [Data Flow](#data-flow) section below |
| Add a new Django app | Follow the [Adding a New App](#adding-a-new-app) checklist |
| Deploy locally with Docker | `docker compose up --build` |
| Configure environment | Copy `.env.example` → `.env`, see [Environment & Configuration](#environment--configuration) |

---

## Directory Tree

```
mini-erp/
│
├── apps/                              # ─── Domain Applications ───
│   │
│   ├── finance/                       # Payables, Receivables, Expenses
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   └── 0002_add_expense_models.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── accounts_payable_service.py
│   │   │   ├── expense_service.py
│   │   │   ├── report_service.py
│   │   │   └── stock_report_service.py
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── factories.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── inventory/                     # Products, Variants, Stock, COGS
│   │   ├── constants/
│   │   │   ├── __init__.py
│   │   │   └── categories.py          # Master category mappings (Shopee, TikTok)
│   │   ├── management/
│   │   │   └── commands/
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_add_sku_sequence_and_triggers.py
│   │   │   ├── 0003_stockmovement_field_change.py
│   │   │   ├── 0004_productcogs_reference_number_and_more.py
│   │   │   ├── 0005_add_allocated_fees_to_product_cogs.py
│   │   │   └── 0006_category_master_category_key_productphoto.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── bulk_inventory_service.py
│   │   │   ├── inventory_service.py
│   │   │   └── product_service.py
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── factories.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── omnichannel/                   # Marketplace Integrations
│   │   ├── vendor/
│   │   │   ├── shopee/
│   │   │   ├── tiktok/
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── purchasing/                    # Purchase Orders & Receiving
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_add_po_number_sequence_and_triggers.py
│   │   │   ├── 0003_invoice.py
│   │   │   ├── 0004_delete_invoice_purchaseorderdetail_updated_qty.py
│   │   │   ├── 0005_rename_comission_fee_pct_....py
│   │   │   ├── 0006_rename_total_qty_to_total_ordered_qty.py
│   │   │   └── 0007_alter_purchaseorder_status.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── purchasing_service.py
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── factories.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   └── sales/                         # Sales Orders, Returns, COGS
│       ├── migrations/
│       │   ├── 0001_initial.py
│       │   ├── 0002_add_so_return_number_sequences.py
│       │   └── 0003_salesorder_source_platform.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── cogs_consumption.py
│       │   └── sales_service.py
│       ├── __init__.py
│       ├── admin.py
│       ├── factories.py
│       ├── models.py
│       ├── serializers.py
│       ├── tests.py
│       ├── urls.py
│       └── views.py
│
├── core/                              # ─── Shared Infrastructure ───
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   └── 0002_add_user_profile.py
│   ├── __init__.py
│   ├── admin.py
│   ├── asgi.py
│   ├── factories.py
│   ├── models.py                      # Company, DefaultModel, Marketplace, UserProfile
│   ├── permissions.py
│   ├── serializers.py
│   ├── settings.py
│   ├── test_settings.py
│   ├── urls.py                        # Root routing: JWT auth + all app includes
│   ├── utils.py                       # ULID gen, PDF validation/compression, shipping config
│   ├── views.py
│   └── wsgi.py
│
├── fixtures/                          # ─── Seed Data ───
│   ├── __init__.py
│   ├── README.md
│   └── seed_data.py
│
├── k8s/                               # ─── Kubernetes Manifests ───
│   ├── django-app.yaml
│   └── postgres.yaml
│
├── .dockerignore
├── .env / .env.example
├── .gitignore
├── .gitlab-ci.yml                     # ruff → mypy → pytest (postgres service)
├── .pre-commit-config.yaml            # ruff fix/format + mypy
├── .python-version
├── conftest.py
├── docker-compose.test.yml
├── docker-compose.yml                 # Postgres 15 + migration service
├── Dockerfile                         # Multi-stage: uv builder → python:3.12-slim
├── entrypoint.sh / entrypoint-k8s.sh
├── local_deploy.sh
├── main.py
├── manage.py
├── mypy.ini
├── Overview Product README.md
├── pyproject.toml                     # uv deps, ruff, mypy config
├── pytest.ini
├── README.md
├── run-mypy
├── uv.lock
└── wait_for_db.py
```

---

## Domain Apps

### `apps/finance/` — Accounts Payable, Receivable & Expenses

Tracks financial obligations and income.

| Model | Purpose | Key Fields |
|---|---|---|
| `AccountsPayable` | PO payment tracking (auto-created when PO → ORDERED) | `purchase_order` (OTO), `total_amount`, `paid_amount`, `status` (UNPAID/PARTIAL/PAID), `due_date` |
| `PaymentRecord` | Individual payments against an AP | `accounts_payable` (FK), `amount`, `payment_date`, `payment_method` (TRANSFER/CASH/EWALLET), `proof_file` |
| `AccountsReceivable` | Marketplace settlement tracking (auto-created when SO → COMPLETED) | `sales_order` (OTO), `expected_amount`, `settled_amount`, `status` (PENDING/SETTLED) |
| `ExpenseCategory` | Expense classification | `name`, `description`, `is_active` (unique per company) |
| `Expense` | Operational expenses | `expense_number` (auto), `category` (FK), `amount`, `expense_date`, `payment_method`, `receipt_file`, `is_recurring` |

**Services** (`services/`):
- `AccountsPayableService` — `create_payable_from_po()`, `record_payment()` (with over-payment guard), `get_outstanding()`, `create_receivable_from_so()`, `settle_receivable()`
- `ExpenseService` — CRUD with category validation
- `ReportService` — Aggregation/reporting queries
- `StockReportService` — Inventory valuation report

---

### `apps/inventory/` — Products, Stock & COGS

Core catalog and inventory engine with FIFO costing.

| Model | Purpose | Key Fields |
|---|---|---|
| `Category` | Product category | `name`, `category_code`, `master_category_key` (maps to Shopee/TikTok) |
| `Product` | SKU-level summary (aggregated from variants) | `name`, `sku_code` (auto), `total_qty`, `total_cogs`, `variant_options` (JSON), `shipping_config` (JSON), weight/dimensions |
| `ProductPhoto` | Product gallery (up to 9) | `product` (FK), `image`, `order`, `is_primary` |
| `ProductVariant` | Actual inventory unit (size/color) | `product` (FK), `sku_variant_code`, `variant_values` (JSON), `current_cogs`, `base_price`, `total_*_qty`, `is_fake` |
| `Warehouse` | Physical warehouse | `name`, `address`, `is_marketplace_visible` |
| `ProductVariantWarehouse` | Stock per variant per warehouse | `incoming_qty`, `physical_qty`, `checkout_qty`; property: `available_qty` |
| `ProductCogs` | FIFO cost layers per variant/warehouse | `reference_number` (PO#), `purchase_date`, `price_rmb`, `exchange_rate`, `cogs_amount` (IDR), `remaining_qty`, allocated fees |
| `ProductVariantMarketplace` | Pricing per marketplace | `selling_price`, `discounted_price`, `is_active` |
| `StockMovement` | Audit log of all stock changes | `movement_type` (PUR/IN/OUT/ADJ/TRF/RET), `quantity`, `balance_before`, `balance_after`, `reference_number` |

**Services** (`services/`):
- `InventoryService` — `record_single_stock_movement()`, `record_multiple_stock_movements()`, `update_stock_on_po()` (handles ORDERED/DELIVERED/COMPLETED transitions), `update_cogs_on_po()` (creates/updates FIFO layers with volume-based shipping allocation)
- `ProductService` — Product + variant CRUD, SKU generation
- `BulkInventoryService` — Batch import/export operations

**Sub-modules:**
- `constants/categories.py` — Maps internal category keys to Shopee (`MASTER_CATEGORY_SHOPEE`) and TikTok (`MASTER_CATEGORY_TIKTOK`) category IDs
- `management/commands/` — Custom Django management commands

---

### `apps/purchasing/` — Purchase Orders & Receiving

End-to-end PO lifecycle from draft to completion.

| Model | Purpose | Key Fields |
|---|---|---|
| `PurchaseOrder` | Purchase order (status machine) | `purchase_order_number` (auto: PO-YYYY-NNN), `status` (DRAFT→ORDERED→SHIPPED→DELIVERED→COMPLETED), `supplier_name`, `forwarder_name`, `commission_fee_pct`, `delivery_fee` (RMB), `exchange_rate` (IDR), `shipping_fee`, `procure_amount`, `total_amount`, file fields for invoices/DO/packing |
| `PurchaseOrderDetail` | Line items on a PO | `ordered_qty`, `received_qty`, `updated_qty`, `unit_price_foreign` (RMB), `unit_price_base` (IDR), `discounted_*` fields, `incoming_qty`, `stock_on_hand`, `avg_sales` |

**Services** (`services/`):
- `PurchaseOrderService` — `create_purchase_order()`, `update_purchase_order()` (enforces status transitions, validates price field immutability after ORDERED, validates received_qty decreases against physical stock, triggers inventory/cogs/AP updates on transitions)

---

### `apps/sales/` — Sales Orders & Returns

Order management with FIFO COGS consumption and marketplace support.

| Model | Purpose | Key Fields |
|---|---|---|
| `SalesOrder` | Sales order (status machine) | `order_number` (auto: SO-YYYY-NNN), `marketplace` (FK), `source_platform` (SHOPEE/TIKTOK/MANUAL), `status` (PENDING→CONFIRMED→SHIPPING→DELIVERED→COMPLETED→RETURNED), `warehouse`, `customer_*`, `shipping_*`, `order_date` through `completed_date`, `courier_name`, `tracking_number`, financial fields (`subtotal`, `total_discount`, `net_revenue`, `gross_profit`, etc.) |
| `SalesOrderItem` | Line items on an SO | `product_variant` (FK), `quantity`, `selling_price`, `discount_amount`, `commission_fee`, `service_fee`, `total_marketplace_fee`, `actual_cogs_per_unit`, `actual_cogs_total`, `line_total` |
| `SalesOrderCogsDetail` | FIFO consumption record | `sales_order_item` (FK), `product_cogs` (FK), `quantity_consumed`, `cogs_per_unit`, `total_cogs` |
| `SalesReturn` | Customer return | `return_number` (auto), `sales_order` (FK), `status` (REQUESTED→APPROVED→RECEIVED→REJECTED), `refund_amount` |
| `SalesReturnItem` | Return line items | `sales_order_item` (FK), `product_variant` (FK), `quantity`, `reversed_cogs_total` |

**Services** (`services/`):
- `SalesOrderService` — `create_sales_order()`, `update_sales_order()` (status machine with validation), `confirm_order()` (deducts stock, consumes FIFO COGS, creates outbound movements), `cancel_order()` (reverses stock and COGS), `_recalculate_totals()`
- `SalesReturnService` — `create_return()` (validates qty against already-returned), `receive_return()` (restores stock, partial FIFO reversal, updates AR)
- `CogsConsumptionService` — `consume_fifo()` (oldest layers first via `purchase_date ASC`), `reverse_fifo()` (full reversal for cancellation), `partial_reverse_fifo()` (LIFO reversal of FIFO consumption for returns)

---

### `apps/omnichannel/` — Marketplace Integrations

Integration adapters for external sales channels. This app is the bridge between mini-erp and external marketplace APIs. Each vendor is a self-contained sub-package with its own models, API clients, serializers, views, and URL routing.

| Directory | Purpose | Key Responsibilities |
|---|---|---|
| `vendor/shopee/` | Shopee API integration | Order sync, product listing push/pull, shipping label retrieval, webhook handling |
| `vendor/tiktok/` | TikTok Shop API integration | Order sync, product listing, fulfillment updates, webhook handling |

**Intended architecture (per vendor):**

```
vendor/<platform>/
├── __init__.py
├── admin.py
├── api_client.py          # HTTP client wrapping the platform's REST API
├── auth.py                # OAuth / token management & refresh
├── factories.py
├── migrations/
├── models.py              # Shop-specific models (e.g., ShopeeShop, TikTokShop)
├── serializers.py
├── tests.py
├── urls.py
├── views.py
└── webhooks.py            # Webhook payload validation & dispatch
```

Each vendor sub-package is registered as a Django app in `INSTALLED_APPS` and wired into `core/urls.py`. Vendors share the `MarketplaceConnection` model in `core.models` to link platform shops to companies.

**Current state:** Scaffolding in place — vendor directories are created with basic structure. Platform-specific adapters are partially implemented. See each vendor's module for current progress.

---

## Service Layer Convention

### Why `services/` exists

Business logic lives in service classes, not in views or models. This keeps:

- **Views thin** — they only parse requests, delegate to services, and return responses
- **Models thin** — they define data structure, constraints, and trivial properties only
- **Logic testable** — services can be unit-tested without HTTP or Django request objects
- **Logic reusable** — the same service method can be called from a view, a management command, a Celery task, or a shell session

### Naming convention

- File: `<domain>_service.py` (e.g. `purchasing_service.py`, `accounts_payable_service.py`)
- Class: `PascalCase<Domain>Service` (e.g. `PurchaseOrderService`, `AccountsPayableService`)
- Methods are plain Python — they accept primitives, model instances, or dicts, never `request` objects

### What belongs where

| Layer | Responsibility |
|---|---|
| **Model** | Field definitions, constraints (`unique_together`, `choices`), properties (`@property`), `__str__`, simple helpers that operate on a single instance |
| **Service** | Business logic involving multiple models, transaction boundaries (`@transaction.atomic`), cross-model coordination, external calls, validations that span objects |
| **View** | HTTP parsing, permission checks, serializer validation, calling services, returning responses |
| **Serializer** | Input validation, field formatting, nested create/update logic |

### Service skeleton

```python
from django.db import transaction


class InventoryService:
    """Business logic for inventory operations."""

    @transaction.atomic
    def record_stock_movement(
        self, variant_id: str, warehouse_id: str, qty: int, movement_type: str
    ) -> dict:
        """Execute a stock movement and return the resulting balance."""
        # 1. Validate business rules
        # 2. Lock rows (select_for_update)
        # 3. Perform mutations
        # 4. Create audit trail (StockMovement)
        # 5. Return result
        ...
```

### Transaction discipline

Methods that mutate multiple rows **must** be decorated with `@transaction.atomic`. Services use `select_for_update()` to lock rows and prevent race conditions during concurrent operations (e.g., stock deduction).

---

## Core Infrastructure

### `core/` — Shared Base

| File | Purpose |
|---|---|
| `models.py` | `TimeStampedModel` (abstract, `cdate`/`udate`), `DefaultModel` (adds `company` FK), `Company`, `Marketplace` (with `shipping_config` JSON), `UserProfile` (RBAC: admin/cs/warehouse/finance/viewer), `MarketplaceConnection` (links Shopee/TikTok shops to companies) |
| `utils.py` | `generate_ulid()`, `round_decimal()`, `get_default_shipping_config()` (Indonesia courier config with marketplace-specific carriers), `is_valid_pdf()` (size+header+structure), `compress_pdf_file()` (PyMuPDF with configurable quality levels) |
| `urls.py` | JWT auth (`/api/token/`, `/api/token/refresh/`), `/api/profile/`, DefaultRouter for `Company`/`Marketplace`/`MarketplaceConnection` view sets, includes for all 5 app URL configs |
| `settings.py` | Django + DRF + SimpleJWT + CORS + django-storages (R2/S3) + database |
| `permissions.py` | Custom DRF permission classes |
| `factories.py` | factory-boy factories for core models |

---

## Adding a New App

Steps to scaffold and wire up a new Django app following mini-erp conventions.

### 1. Scaffold the app

```bash
uv run django-admin startapp <app_name> apps/<app_name>
```

### 2. Create required directories and files

```bash
mkdir -p apps/<app_name>/services
touch apps/<app_name>/services/__init__.py
touch apps/<app_name>/factories.py
```

Ensure the final structure:

```
apps/<app_name>/
├── __init__.py
├── admin.py
├── factories.py
├── migrations/
│   └── __init__.py
├── models.py
├── serializers.py
├── services/
│   ├── __init__.py
│   └── <domain>_service.py
├── tests.py
├── urls.py
└── views.py
```

### 3. Register in settings

Add to `INSTALLED_APPS` in `core/settings.py`:

```python
"apps.<app_name>",
```

### 4. Wire up URLs

Create `apps/<app_name>/urls.py` with your view routes, then include it in `core/urls.py`:

```python
path("api/<prefix>/", include("apps.<app_name>.urls")),
```

### 5. Add models and migrations

Define models in `models.py`, then:

```bash
uv run python manage.py makemigrations <app_name>
uv run python manage.py migrate
```

### 6. Create service classes

Add business logic in `services/<domain>_service.py`. Follow the [Service Layer Convention](#service-layer-convention).

### 7. Add serializers

Define DRF serializers in `serializers.py` — one per model or use-case.

### 8. Create factories

Add factory-boy factories in `factories.py` for all models. This ensures tests can create data concisely.

### 9. Write tests

Write service tests in `tests.py`. Test the service methods directly — views tests are secondary.

### 10. Register in admin

Register models in `admin.py` for back-office access.

### 11. Run quality checks

```bash
uv run ruff check apps/<app_name>
uv run mypy apps/<app_name>
uv run pytest apps/<app_name>/tests.py
```

---

## Infrastructure & Operations

### Docker

```
Dockerfile          # Multi-stage: uv sync (builder) → python:3.12-slim (runtime)
docker-compose.yml  # postgres:15 + migration service
```

**Dockerfile stages:**
1. **Builder** — `python:3.12-slim` + `uv`, installs deps via `uv sync --frozen --no-dev`, copies code
2. **Runtime** — `python:3.12-slim`, copies `.venv` + code from builder, runs `entrypoint.sh` → gunicorn

### Kubernetes (`k8s/`)
- `django-app.yaml` — Django deployment + service
- `postgres.yaml` — PostgreSQL stateful set + service

### CI/CD (`.gitlab-ci.yml`)
| Stage | Job | Command |
|---|---|---|
| quality | `ruff-imports` | `uv run ruff check --select I --diff` |
| quality | `ruff-format` | `uv run ruff format --check` |
| quality | `ruff-lint` | `uv run ruff check` |
| quality | `mypy` | `uv run mypy --config-file mypy.ini` |
| test | `pytest` | `uv run pytest` (with postgres:15-alpine service) |

### Environment & Configuration

Copy `.env.example` to `.env` and fill in the values below.

#### Django

| Variable | Example | Description |
|---|---|---|
| `SECRET_KEY` | `django-insecure-...` | Django secret key (generate via `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`) |
| `DEBUG` | `True` | Enable debug mode for local dev |
| `DJANGO_SETTINGS_MODULE` | `core.settings` | Django settings module |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS origins |

#### Database

| Variable | Example | Description |
|---|---|---|
| `DB_NAME` | `mini_erp` | PostgreSQL database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DATABASE_URL` | `postgres://postgres:postgres@localhost:5432/mini_erp` | Alternative: full connection string (overrides individual `DB_*` vars) |

#### Storage (R2 / S3)

| Variable | Example | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `...` | R2/S3 access key |
| `AWS_SECRET_ACCESS_KEY` | `...` | R2/S3 secret key |
| `AWS_STORAGE_BUCKET_NAME` | `mini-erp-uploads` | Bucket name |
| `AWS_S3_ENDPOINT_URL` | `https://<account>.r2.cloudflarestorage.com` | Endpoint URL (R2-specific; omit for AWS S3) |
| `AWS_DEFAULT_ACL` | `private` | Object ACL |
| `AWS_QUERYSTRING_AUTH` | `True` | Sign URLs with expiration |
| `AWS_QUERYSTRING_EXPIRE` | `3600` | URL expiration in seconds |

#### JWT

| Variable | Example | Description |
|---|---|---|
| `SIMPLE_JWT_SECRET` | `...` | JWT signing key (falls back to `SECRET_KEY` if not set) |
| `SIMPLE_JWT_ACCESS_TTL` | `60` | Access token lifetime in minutes |
| `SIMPLE_JWT_REFRESH_TTL` | `1440` | Refresh token lifetime in minutes |

### main.py vs manage.py

Both files are entry points into the Django project, but they serve different runtimes:

- **`manage.py`** — Used during **development**. The standard Django management script. Run commands like `uv run python manage.py runserver`, `uv run python manage.py makemigrations`, `uv run python manage.py shell`. Also used for `django-admin` commands in development.
- **`main.py`** — Used for **production ASGI serving**. Created by `uv init` as the default module entry point. Not used directly — uvicorn/gunicorn target `core.asgi:application` or `core.wsgi:application`. Kept in the project root for tooling compatibility.

### Code Quality
- **`.pre-commit-config.yaml`** — Pre-commit hooks: `ruff --fix`, `ruff-format`, `mypy`
- **`pyproject.toml`** — Ruff: `F` + `I` rule sets, 100 char line length, double quotes, isort configured. Mypy: `mypy_django_plugin`
- **`mypy.ini`** — Strict typing configuration with django-stubs
- **`pytest.ini`** — `DJANGO_SETTINGS_MODULE=core.test_settings`, migration-based DB, deprecation warning filters

---

## Data Flow

```
Purchasing ──→ Inventory ──→ Sales ──→ Finance

PO ORDERED     Stock In       SO Confirmed     AP/AR Created
  │               │               │               │
  │         ┌─────┘               │               │
  ▼         ▼                     ▼               ▼
Accounts   ProductCogs     CogsConsumption   AccountsPayable
Payable    (FIFO layers)   (FIFO consume)    (from PO ORDERED)
(from PO                                                   
 ORDERED)                   SO Completed     AccountsReceivable
                              │               (from SO COMPLETED)
                              ▼
                           SalesReturn
                           (FIFO reverse)
```

1. **PO ORDERED** → Creates `AccountsPayable`, creates `StockMovement` (incoming)
2. **PO DELIVERED** → Creates `ProductCogs` FIFO layers with volume-based shipping allocation, updates `ProductVariantWarehouse.physical_qty`
3. **SO CONFIRMED** → Deducts stock, consumes FIFO `ProductCogs` layers (oldest first), creates `SalesOrderCogsDetail`, creates outbound `StockMovement`
4. **SO COMPLETED** → Creates `AccountsReceivable`
5. **SO CANCELLED** (if confirmed) → Reverses stock deduction, reverses COGS consumption, creates return `StockMovement`
6. **Sales Return received** → Partial FIFO reversal (LIFO order), restores stock, updates AR
7. **Payment recorded** → Updates `AccountsPayable.paid_amount`, transitions status UNPAID→PARTIAL→PAID

---

## Testing

- **Framework**: pytest + pytest-django
- **Factories**: factory-boy per app (`factories.py`)
- **Fixtures**: `fixtures/seed_data.py`
- **Conftest**: `conftest.py` (root-level shared fixtures)
- **Settings**: `core/test_settings.py` (separate from production settings)
- **Coverage**: Per-app `tests.py` files covering services (primary) and views (secondary)
