# # inventory/services/product_service.py
# from django.db import transaction

# from inventory.models import (
#     Category,
#     Product,
#     ProductVariant,
#     ProductVariantMarketplace,
#     ProductVariantWarehouse,
# )


# class ProductService:
#     @staticmethod
#     @transaction.atomic
#     def create_product_with_variants(product_data, variants_data, marketplaces=None):
#         """
#         Create a product with all its variants and marketplace listings

#         Args:
#             product_data: dict with product fields
#             variants_data: list of dicts with variant fields
#             marketplaces: list of Marketplace objects to list on

#         Returns:
#             Product instance
#         """

#         # 1. Create product
#         product = Product.objects.create(
#             name=product_data["name"],
#             sku_code=product_data["sku_code"],
#             description=product_data.get("description", ""),
#             total_qty=0,
#             total_cogs=0,
#         )

#         # 2. Create variants
#         for variant_data in variants_data:
#             variant = ProductVariant.objects.create(
#                 product=product,
#                 name=variant_data["name"],
#                 sku_variant_code=variant_data["sku_variant_code"],
#                 selling_price=variant_data["selling_price"],
#                 current_cogs=0,
#                 total_incoming_qty=0,
#                 total_outgoing_qty=0,
#                 total_available_qty=0,
#             )

#             # 3. Create warehouse stock entries (optional)
#             if "warehouses" in variant_data:
#                 for warehouse in variant_data["warehouses"]:
#                     ProductVariantWarehouse.objects.create(
#                         product_variant=variant,
#                         warehouse=warehouse,
#                         incoming_qty=0,
#                         outgoing_qty=0,
#                         physical_stock=0,
#                         checkout_qty=0,
#                     )

#             # 4. Create marketplace listings (optional)
#             if marketplaces:
#                 for marketplace in marketplaces:
#                     ProductVariantMarketplace.objects.create(
#                         product_variant=variant, marketplace=marketplace, is_active=True
#                     )

#         return product

#     @staticmethod
#     @transaction.atomic
#     def create_simple_product(name, sku_code, description=""):
#         """Create a basic product without variants (for simple use cases)"""

#         product = Product.objects.create(
#             name=name, sku_code=sku_code, description=description, total_qty=0, total_cogs=0
#         )

#         return product
