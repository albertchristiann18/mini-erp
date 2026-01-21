from typing import Any

from django.db import models
from django_ulid.models import ULIDField, default

from core.models import DefaultModel, Marketplace


class Category(DefaultModel):
    """Product category"""

    id = ULIDField(primary_key=True, default=default, editable=False, db_column="category_id")
    name = models.CharField(max_length=255, unique=True)
    category_code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Product(DefaultModel):
    """SKU-level summary (aggregated from all variants)"""

    id = ULIDField(primary_key=True, default=default, editable=False, db_column="product_id")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    sku_code = models.CharField(max_length=100, unique=True, editable=False)

    # Summary fields (calculated from all ProductVariants)
    total_qty = models.BigIntegerField(default=0)  # Sum of all variant.total_available_qty
    total_cogs = models.BigIntegerField(default=0)  # Sum of all variant COGS value
    # Note: No total_selling_price here - price varies by marketplace!

    # Stores the structure: [{"name": "Warna", "order": 1}, {"name": "Size", "order": 2}]
    variant_options = models.JSONField(default=list, blank=True)

    # This will store: {"Bahan": ["Katun", "Bulu Domba"], "Motif": ["Batik"]}
    specifications = models.JSONField(default=dict, blank=True)

    # Image 4: "Pengiriman" - Usually stays at Product level unless variants differ in size
    weight = models.PositiveIntegerField(default=0)
    length = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    @staticmethod
    def get_default_shipping_config() -> dict:
        return {
            "insurance": {"is_required": False, "fee_type": "percentage"},
            "general": {
                "reguler": {
                    "cod": True,
                    "expeditions": [
                        {
                            "code": "anteraja_reguler",
                            "name": "Anteraja Reguler",
                            "is_active": False,
                        },
                        {"code": "id_express", "name": "ID Express", "is_active": False},
                        {"code": "jne", "name": "JNE Reguler", "is_active": False},
                        {"code": "ninja_xpress", "name": "Ninja Xpress", "is_active": False},
                        {"code": "pos_reguler", "name": "Pos Reguler", "is_active": False},
                        {"code": "sicepat", "name": "SiCepat REG", "is_active": False},
                        {"code": "jnt", "name": "J&T Express", "is_active": False},
                        {"code": "express", "name": "Express", "is_active": False},
                    ],
                },
                "instant": {
                    "cod": False,
                    "expeditions": [
                        {"code": "grab", "name": "GrabExpress", "is_active": False},
                        {"code": "gojek", "name": "GoSend Instant", "is_active": False},
                    ],
                },
                "instant_priority": {
                    "cod": False,
                    "expeditions": [
                        {
                            "code": "grab",
                            "name": "GrabExpress Instant Prioritas",
                            "is_active": False,
                        },
                        {"code": "gojek", "name": "GoSend Instant Prioritas", "is_active": False},
                    ],
                },
                "cargo": {
                    "cod": False,
                    "expeditions": [
                        {"code": "anteraja_cargo", "name": "Anteraja Cargo", "is_active": False},
                        {
                            "code": "anteraja_economy",
                            "name": "Anteraja Economy",
                            "is_active": False,
                        },
                        {"code": "jnt", "name": "J&T Cargo", "is_active": False},
                        {"code": "jne", "name": "JNE Trucking (JTR)", "is_active": False},
                        {"code": "sentral_cargo", "name": "Sentral Cargo", "is_active": False},
                        {"code": "sicepat_gokil", "name": "Sicepat Gokil", "is_active": False},
                        {"code": "sicepat_halu", "name": "SiCepat Halu", "is_active": False},
                        {"code": "express_eco", "name": "Express Eco", "is_active": False},
                    ],
                },
                "sameday": {
                    "cod": False,
                    "expeditions": [
                        {"code": "anteraja", "name": "Anteraja Sameday", "is_active": False},
                        {"code": "grab", "name": "GrabExpress Sameday", "is_active": False},
                        {"code": "gojek", "name": "GoSend Same Day", "is_active": False},
                    ],
                },
                "nextday": {
                    "cod": False,
                    "expeditions": [
                        {"code": "jne", "name": "JNE YES", "is_active": False},
                        {"code": "sicepat", "name": "Sicepat BEST", "is_active": False},
                    ],
                },
            },
            "marketplaces": {
                "Shopee": {
                    "reguler": {
                        "expeditions": [
                            {"code": "spx_standard", "name": "SPX Standard", "is_active": False}
                        ]
                    },
                    "cargo": {
                        "expeditions": [
                            {"code": "spx_hemat", "name": "SPX Hemat", "is_active": False}
                        ]
                    },
                    "instant": {
                        "expeditions": [
                            {"code": "spx_instant", "name": "SPX Instant", "is_active": False}
                        ]
                    },
                    "instant_priority": {
                        "expeditions": [
                            {
                                "code": "spx_instant_prio",
                                "name": "SPX Instant Prioritas",
                                "is_active": False,
                            }
                        ]
                    },
                    "sameday": {
                        "expeditions": [
                            {"code": "spx_sameday", "name": "SPX Sameday", "is_active": False}
                        ]
                    },
                },
                "Tokopedia_TikTok": {"use_general_config": True},
            },
        }

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
    """Variant of a product (e.g., size, color) - the actual inventory unit"""

    id = ULIDField(
        primary_key=True, default=default, editable=False, db_column="product_variant_id"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=255)
    sku_variant_code = models.CharField(max_length=100, unique=True)

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
    id = ULIDField(primary_key=True, default=default, editable=False, db_column="warehouse_id")

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    is_marketplace_visible = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class ProductVariantWarehouse(DefaultModel):
    """Stock of each variant in each warehouse"""

    id = ULIDField(
        primary_key=True, default=default, editable=False, db_column="product_variant_warehouse_id"
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
    """FIFO inventory layers per variant per warehouse"""

    id = ULIDField(primary_key=True, default=default, editable=False, db_column="product_cogs_id")
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)

    purchase_date = models.DateField()
    price_rmb = models.BigIntegerField()
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=4)
    cogs_amount = models.BigIntegerField()  # In IDR

    original_qty = models.IntegerField(default=0)
    remaining_qty = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["purchase_date"]


class ProductVariantMarketplace(DefaultModel):
    """Pricing per variant per marketplace (stock is unified)"""

    id = ULIDField(
        primary_key=True,
        default=default,
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
