from typing import Any, Dict

from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

from apps.inventory.models import ProductVariant
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from core.utils import is_valid_pdf


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for Purchase Order Details"""

    product_variant_id = serializers.CharField(write_only=True)
    product_variant_name = serializers.CharField(source="product_variant.name", read_only=True)

    class Meta:
        model = PurchaseOrderDetail
        fields = [
            "id",
            "product_variant_id",
            "product_variant_name",
            "ordered_qty",
            "received_qty",
            "unit_price_base",
            "total_price_base",
            "remarks",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data: Dict[str, Any]) -> PurchaseOrderDetail:
        product_variant_id = validated_data.pop("product_variant_id")
        product_variant = ProductVariant.objects.get(id=product_variant_id)
        validated_data["product_variant"] = product_variant
        return super().create(validated_data)  # type: ignore


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """Serializer for listing Purchase Orders (lightweight, no details)"""

    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "purchase_order_number",
            "status",
            "warehouse_name",
            "company_name",
            "supplier_name",
            "total_qty",
            "total_amount",
            "cdate",
            "udate",
        ]
        read_only_fields = ["id", "cdate", "udate"]


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Purchase Orders with nested details"""

    order_details = PurchaseOrderDetailSerializer(many=True, write_only=True, required=True)
    warehouse_id = serializers.CharField(write_only=True)
    company_id = serializers.CharField(write_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "purchase_order_number",
            "warehouse_id",
            "company_id",
            "supplier_name",
            "total_qty",
            "total_amount",
            "order_details",
            "purchase_order_invoice_file",
            "delivery_order_file",
            "delivery_order_invoice_file",
        ]
        extra_kwargs = {
            "purchase_order_number": {"required": False},
            "purchase_order_invoice_file": {"required": False},
            "delivery_order_file": {"required": False},
            "delivery_order_invoice_file": {"required": False},
        }
        read_only_fields = ["purchase_order_number"]

    def validate(self, attrs: dict) -> dict:
        if attrs.get("status") and attrs.get("status") != PurchaseOrder.POStatus.DRAFT:
            raise serializers.ValidationError(
                {"status": "Purchase Order must be created with DRAFT status"}
            )
        return attrs

    def validate_purchase_order_invoice_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)

        return value

    def validate_delivery_order_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)

        return value

    def validate_delivery_order_invoice_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)
        return value


class PurchaseOrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Purchase Orders and Details"""

    order_details = PurchaseOrderDetailSerializer(many=True, required=False)
    warehouse_id = serializers.CharField(write_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "purchase_order_number",
            "status",
            "warehouse_id",
            "supplier_name",
            "total_qty",
            "total_amount",
            "invoice_number",
            "delivery_date",
            "order_details",
            "purchase_order_invoice_file",
            "delivery_order_file",
            "delivery_order_invoice_file",
        ]
        extra_kwargs = {
            "purchase_order_number": {"required": False},
            "purchase_order_invoice_file": {"required": False},
            "delivery_order_file": {"required": False},
            "delivery_order_invoice_file": {"required": False},
        }

    def validate_purchase_order_invoice_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)

        return value

    def validate_delivery_order_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)

        return value

    def validate_delivery_order_invoice_file(self, value: UploadedFile) -> UploadedFile:
        if not value:
            raise serializers.ValidationError("No file provided.")

        is_valid, error_msg = is_valid_pdf(value, max_size_mb=2)
        if not is_valid:
            raise serializers.ValidationError(error_msg)

        return value


class PurchaseOrderReadSerializer(serializers.ModelSerializer):
    """Serializer for reading Purchase Orders with all details"""

    order_details = PurchaseOrderDetailSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "purchase_order_number",
            "status",
            "warehouse_name",
            "company_name",
            "supplier_name",
            "total_qty",
            "total_amount",
            "invoice_number",
            "delivery_date",
            "order_details",
            "cdate",
            "udate",
        ]
        read_only_fields = ["id", "cdate", "udate"]
