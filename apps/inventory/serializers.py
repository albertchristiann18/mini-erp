from typing import Any

from django.db import transaction
from rest_framework import serializers

from apps.inventory.models import (
    Category,
    Product,
    ProductVariant,
    ProductVariantMarketplace,
    Warehouse,
)
from core.models import Company, Marketplace


class CategorySerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company.id", read_only=True)

    class Meta:
        model = Category
        # '__all__' includes all fields: id, name, category_code, description, is_active
        fields = "__all__"


class WarehouseSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company.id", read_only=True)

    class Meta:
        model = Warehouse
        # '__all__' includes all fields: id, name, category_code, description, is_active
        fields = "__all__"


class VariantMarketplaceSerializer(serializers.ModelSerializer):
    marketplace_id = serializers.UUIDField(source="marketplace.id", read_only=True)

    class Meta:
        model = ProductVariantMarketplace
        fields = ["marketplace_id", "selling_price", "discounted_price", "is_active"]


class VariantSerializer(serializers.ModelSerializer):
    # Nest the marketplace pricing inside the variant
    marketplace_listings = VariantMarketplaceSerializer(many=True)

    class Meta:
        model = ProductVariant
        fields = [
            "name",
            "sku_variant_code",
            "variant_values",
            "base_price",
            "marketplace_listings",
            "is_active",
        ]


class ProductSerializer(serializers.ModelSerializer):
    # Keep your read-only ID fields
    company_id = serializers.UUIDField(source="company.id", read_only=True)
    category_id = serializers.UUIDField(source="category.id", read_only=True)

    # Add the nested variants
    # The name 'variants' must match the related_name in your ProductVariant model
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        # Explicitly listing fields is often safer when nesting
        fields = [
            "id",
            "company_id",
            "category_id",
            "name",
            "description",
            "sku_code",
            "total_qty",
            "total_cogs",
            "variant_options",
            "specifications",
            "weight",
            "length",
            "width",
            "height",
            "is_active",
            "variants",  # Include the nested field here
        ]


class VariantMarketplaceCreateSerializer(serializers.ModelSerializer):
    marketplace_id = serializers.CharField(write_only=True)

    class Meta:
        model = ProductVariantMarketplace
        fields = ["marketplace_id", "selling_price", "discounted_price"]

    def validate_marketplace_id(self, value: Any) -> Any:
        if not Marketplace.objects.filter(id=value).exists():
            raise serializers.ValidationError("Marketplace not found")
        return value


class VariantCreateSerializer(serializers.ModelSerializer):
    marketplace_listings = VariantMarketplaceCreateSerializer(many=True)

    class Meta:
        model = ProductVariant
        fields = [
            "name",
            "sku_variant_code",
            "variant_values",
            "base_price",
            "marketplace_listings",
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    company_id = serializers.CharField(write_only=True)
    category_id = serializers.CharField(write_only=True)
    variants = VariantCreateSerializer(many=True)

    class Meta:
        model = Product
        fields = [
            "company_id",
            "category_id",
            "name",
            "description",
            "variant_options",
            "specifications",
            "weight",
            "length",
            "width",
            "height",
            "variants",
        ]

    def validate_company_id(self, value: Any) -> Any:
        # Return the value (the ID string) exactly as it was passed.
        if not Company.objects.filter(id=value).exists():
            raise serializers.ValidationError("Company not found")
        return value

    def validate_category_id(self, value: Any) -> Any:
        if not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError("Category not found")
        return value

    def create(self, validated_data: dict) -> Product:
        # 1. Extract nested data
        variants_data = validated_data.pop("variants")

        # 2. Extract company (assuming it's passed in the request)
        company_id = validated_data.get("company_id", "")

        with transaction.atomic():
            # 3. Create the Parent Product
            # The DB trigger 'trg_generate_sku' fires here!
            product = Product.objects.create(**validated_data)

            for variant_data in variants_data:
                # 4. Extract marketplace nested data
                listings_data = variant_data.pop("marketplace_listings")

                # 5. Create the ProductVariant
                # The DB trigger 'trg_generate_variant_sku' fires here!
                variant = ProductVariant.objects.create(
                    product=product, company_id=company_id, **variant_data
                )

                # 6. Create the Marketplace Listings
                for listing_data in listings_data:
                    ProductVariantMarketplace.objects.create(
                        product_variant=variant, company_id=company_id, **listing_data
                    )

            return product
