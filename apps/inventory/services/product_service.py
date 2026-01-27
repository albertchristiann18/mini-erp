from django.db import transaction

from apps.inventory.models import (
    Product,
    ProductVariant,
    ProductVariantMarketplace,
)


class ProductService:
    @transaction.atomic
    def create_product_with_variants(self, validated_data: list) -> None:
        company_id = validated_data[0].get("company_id", "")

        # with transaction.atomic():
        products = [
            Product(
                company_id=company_id,
                category_id=data.get("category_id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                specifications=data.get("specifications", {}),
                weight=data.get("weight", 0),
                length=data.get("length", 0),
                width=data.get("width", 0),
                height=data.get("height", 0),
            )
            for data in validated_data
        ]
        created_products = Product.objects.bulk_create(products, batch_size=100)

        product_index_map = {i: obj.id for i, obj in enumerate(created_products)}

        listings_data_tupple = []
        variants = []
        variant_index = 0
        for i in range(len(validated_data)):
            data = validated_data[i]
            variants_data = data.pop("variants")
            for variant_data in variants_data:
                for listing_data in variant_data["marketplace_listings"]:
                    listings_data_tupple.append((variant_index, listing_data))

                variants.append(
                    ProductVariant(
                        product_id=product_index_map[i],
                        company_id=company_id,
                        name=variant_data.get("name", ""),
                        variant_values=variant_data.get("variant_values", {}),
                        base_price=variant_data.get("base_price", 0),
                    )
                )
                variant_index += 1

        created_variants = ProductVariant.objects.bulk_create(variants, batch_size=100)
        variant_index_map = {i: obj.id for i, obj in enumerate(created_variants)}
        create_listing_data = []
        for i, listing_data in listings_data_tupple:
            create_listing_data.append(
                ProductVariantMarketplace(
                    product_variant_id=variant_index_map[i],
                    company_id=company_id,
                    marketplace_id=listing_data["marketplace_id"],
                    selling_price=listing_data["selling_price"],
                    discounted_price=listing_data.get("discounted_price"),
                )
            )
        ProductVariantMarketplace.objects.bulk_create(create_listing_data, batch_size=100)
