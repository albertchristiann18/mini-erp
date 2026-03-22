from typing import Any

from django.db import models
from django_ulid.models import ULIDField

from core.models import DefaultModel, Marketplace
from core.utils import generate_ulid, get_default_shipping_config


class Category(DefaultModel):
    """Product category"""

    id = ULIDField(primary_key=True, default=generate_ulid, editable=False, db_column="category_id")
    name = models.CharField(max_length=255, unique=True)
    category_code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Product(DefaultModel):
    """
    SKU-level summary (aggregated from all variants).
    """

    id = ULIDField(primary_key=True, default=generate_ulid, editable=False, db_column="product_id")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # SKU CODE auto-generated format: {CATEGORY_CODE}-{SEQUENCE_NUMBER} (e.g., KEMEJA-001, KEMEJA-002)
    sku_code = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
    )

    # Summary fields (calculated from all ProductVariants)
    total_qty = models.IntegerField(default=0)  # Sum of all variant.total_available_qty
    total_cogs = models.IntegerField(default=0)  # Sum of all variant COGS value
    # Note: No total_selling_price here - price varies by marketplace!

    # Stores the structure: [{"name": "Warna", "order": 1}, {"name": "Size", "order": 2}]
    variant_options = models.JSONField(default=list, blank=True)

    # This will store: {"Bahan": ["Katun", "Bulu Domba"], "Motif": ["Batik"]}
    specifications = models.JSONField(default=dict, blank=True)

    # TODO handling multiple photos per product and assigned the first photo to be shown
    # TODO handling videos per product
    product_photo = models.FileField(upload_to="products/photos/", null=True, blank=True)

    # Image 4: "Pengiriman" - Usually stays at Product level unless variants differ in size
    weight = models.IntegerField(default=0)
    length = models.IntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # New Shipping Configuration field
    shipping_config = models.JSONField(
        default=get_default_shipping_config,
        blank=True,
        help_text="Stores marketplace-specific shipping and insurance settings",
    )

    def get_shopee_reguler_shipping(self) -> Any:
        """Combines General Reguler and Shopee-specific Reguler expeditions"""
        general = self.shipping_config.get("general", {}).get("reguler", {}).get("expeditions", [])
        shopee = (
            self.shipping_config.get("marketplaces", {})
            .get("Shopee", {})
            .get("reguler", {})
            .get("expeditions", [])
        )

        # Merge both lists
        return general + shopee

    @property
    def total_cogs_value(self) -> float:
        return self.total_qty * self.total_cogs

    def __str__(self) -> str:
        return f"{self.sku_code}-{self.name}"


class ProductVariant(DefaultModel):
    """
    Variant of a product (e.g., size, color) - the actual inventory unit.
    """

    id = ULIDField(
        primary_key=True, default=generate_ulid, editable=False, db_column="product_variant_id"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=255)
    # SKU CODE auto-generated format: {PARENT_SKU}-{VARIANT_VALUE_1}-{VARIANT_VALUE_2} (e.g., KEMEJA-001-NAVY-L, KEMEJA-001-RED-M)
    sku_variant_code = models.CharField(
        max_length=100,
        unique=True,
    )

    # Stores the values mapped to the order: {"1": "Merah", "2": "100"}
    # This matches the 'order' in the Product.variant_options
    variant_values = models.JSONField(default=dict)

    # COGS (calculated from FIFO layers)
    current_cogs = models.BigIntegerField(default=0)  # latest_cogs

    # Pricing (same across all marketplaces)
    base_price = models.BigIntegerField(default=0)

    # Stock summary (sum across ALL warehouses)
    total_incoming_qty = models.IntegerField(default=0)
    total_outgoing_qty = models.IntegerField(default=0)
    total_available_qty = models.IntegerField(default=0)  # Sum of all warehouse available_qty

    is_active = models.BooleanField(default=True)  # Is this variant active/sellable?
    is_fake = models.BooleanField(default=False)  # For testing purposes only

    def __str__(self) -> str:
        return f"{self.sku_variant_code}-{self.name}"


class Warehouse(DefaultModel):
    id = ULIDField(
        primary_key=True, default=generate_ulid, editable=False, db_column="warehouse_id"
    )

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    is_marketplace_visible = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class ProductVariantWarehouse(DefaultModel):
    """Stock of each variant in each warehouse"""

    id = ULIDField(
        primary_key=True,
        default=generate_ulid,
        editable=False,
        db_column="product_variant_warehouse_id",
    )
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="warehouse_stocks"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="variant_stocks"
    )

    # Stock tracking per warehouse
    incoming_qty = models.IntegerField(default=0)
    outgoing_qty = models.IntegerField(default=0)
    physical_qty = models.IntegerField(default=0)  # Actual stock in this warehouse
    checkout_qty = models.IntegerField(default=0)  # Currently in checkout

    @property
    def available_qty(self) -> int:
        """Stock available for sale"""
        return self.physical_qty - self.checkout_qty

    class Meta:
        unique_together = ["product_variant", "warehouse"]
        indexes = [
            models.Index(fields=["product_variant", "warehouse"]),
        ]


class ProductCogs(DefaultModel):
    """FIFO inventory layers per variant per warehouse.

    This model tracks the cost of goods sold (COGS) for inventory items using FIFO method.

    Fields:
    - reference_number: Identifier for the source document (e.g., PO purchase_order_number)
    - purchase_date: Date from PurchaseOrder.invoice_date
    - price_rmb: Unit price in RMB from PO detail (unit_price_foreign)
    - exchange_rate: Exchange rate from PO (PurchaseOrder.exchange_rate)
    - cogs_amount: Unit price in IDR = price_rmb * exchange_rate
    - allocated_shipping_fee: Shipping fee allocated per unit based on volume (RMB -> IDR)
    - allocated_delivery_fee: Delivery fee allocated per unit (RMB -> IDR)
    - original_qty: Total quantity that came in from the PO (accumulates with each delivery update).
    - remaining_qty: Current available quantity for sales/consumption.
                    This ONLY decreases when there are actual outbound/sales transactions.
    """

    id = ULIDField(
        primary_key=True, default=generate_ulid, editable=False, db_column="product_cogs_id"
    )
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    reference_number = models.CharField(
        max_length=100,
        default="",
        blank=True,
        db_index=True,
        help_text="Source document reference (e.g., PO purchase_order_number)",
    )

    purchase_date = models.DateField(help_text="Date from PurchaseOrder.invoice_date")
    price_rmb = models.DecimalField(
        max_digits=15, decimal_places=4, help_text="Unit price in RMB (unit_price_foreign)"
    )
    exchange_rate = models.BigIntegerField(help_text="Exchange rate from PO (rounded integer)")
    cogs_amount = models.BigIntegerField(help_text="Unit price in IDR = price_rmb * exchange_rate")
    allocated_shipping_fee = models.BigIntegerField(
        default=0, help_text="Shipping fee allocated per unit (IDR)"
    )
    allocated_delivery_fee = models.BigIntegerField(
        default=0, help_text="Delivery fee allocated per unit (IDR)"
    )

    original_qty = models.IntegerField(
        default=0,
        help_text="Total quantity that came in from PO (accumulates with each delivery)",
    )
    remaining_qty = models.IntegerField(
        default=0,
        help_text="Current available quantity. Only decreases on actual sales/outbound.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-purchase_date"]
        indexes = [
            models.Index(fields=["product_variant", "warehouse", "reference_number"]),
        ]


class ProductVariantMarketplace(DefaultModel):
    """Pricing per variant per marketplace (stock is unified)"""

    id = ULIDField(
        primary_key=True,
        default=generate_ulid,
        editable=False,
        db_column="product_variant_marketplace_id",
    )
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="marketplace_listings"
    )
    marketplace = models.ForeignKey(
        Marketplace, on_delete=models.CASCADE, related_name="product_listings"
    )

    # Pricing specific to this marketplace
    selling_price = models.BigIntegerField()  # Regular price
    discounted_price = models.BigIntegerField(null=True, blank=True)  # Sale price

    is_active = models.BooleanField(default=True)  # Is listed on this marketplace?

    class Meta:
        unique_together = ["product_variant", "marketplace"]


class StockMovement(DefaultModel):
    class MovementType(models.TextChoices):
        PURCHASE = "PUR", "Purchase Order"
        INBOUND = "IN", "Inbound (Purchase/Restock)"
        OUTBOUND = "OUT", "Outbound (Sales)"
        ADJUSTMENT = "ADJ", "Stock Adjustment (Manual)"
        TRANSFER = "TRF", "Warehouse Transfer"
        RETURN = "RET", "Customer Return"

    id = ULIDField(
        primary_key=True, default=generate_ulid, editable=False, db_column="stock_movement_id"
    )
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    movement_type = models.CharField(max_length=3, choices=MovementType.choices)
    field_change = models.CharField(max_length=100, default="")  # what field is changed
    quantity = models.IntegerField()  # Use positive for IN, negative for OUT
    reference_number = models.CharField(max_length=100, blank=True, null=True)  # PO# or Order ID
    note = models.TextField(blank=True, null=True)
    balance_before = models.IntegerField()
    balance_after = models.IntegerField()

    class Meta:
        ordering = ["-cdate"]
