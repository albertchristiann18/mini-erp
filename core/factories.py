import factory

from apps.inventory.models import Category, Product, ProductVariant, Warehouse
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from core.models import Company, Marketplace


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = "Test Company"


class MarketplaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Marketplace

    name = "Default Marketplace"


class WarehouseFactory(factory.django.DjangoModelFactory):
    """Factory for creating test Warehouse instances"""

    class Meta:
        model = Warehouse

    name = "Test Warehouse"
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for creating test Product instances"""

    class Meta:
        model = Product

    name = "Test Product"
    category = factory.SubFactory("core.factories.CategoryFactory")  # type: ignore[no-untyped-call]
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]


class ProductVariantFactory(factory.django.DjangoModelFactory):
    """Factory for creating test ProductVariant instances"""

    class Meta:
        model = ProductVariant

    name = "Test Product Variant"
    product = factory.SubFactory(ProductFactory)  # type: ignore[no-untyped-call]
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]
    variant_values = {}


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for creating test Category instances"""

    class Meta:
        model = Category

    name = "Test Category"
    category_code = "TEST"
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]


class PurchaseOrderFactory(factory.django.DjangoModelFactory):
    """Factory for creating test PurchaseOrder instances"""

    class Meta:
        model = PurchaseOrder

    purchase_order_number = factory.Sequence(lambda n: f"PO-{n:04d}")  # type: ignore[no-untyped-call]
    warehouse = factory.SubFactory(WarehouseFactory)  # type: ignore[no-untyped-call]
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]
    supplier_name = "Test Supplier"
    status = "DRAFT"
    total_qty = 100
    total_amount = 1000000


class PurchaseOrderDetailFactory(factory.django.DjangoModelFactory):
    """Factory for creating test PurchaseOrderDetail instances"""

    class Meta:
        model = PurchaseOrderDetail

    purchase_order = factory.SubFactory(PurchaseOrderFactory)  # type: ignore[no-untyped-call]
    product_variant = factory.SubFactory(ProductVariantFactory)  # type: ignore[no-untyped-call]
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]
    ordered_qty = 50
    unit_price_base = 10000
    total_price_base = 500000
