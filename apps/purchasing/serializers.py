from typing import Any, Dict

from rest_framework import serializers

from apps.inventory.models import ProductVariant
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from apps.purchasing.services.purchasing_service import PurchaseOrderService


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
        ]

    def create(self, validated_data: dict) -> PurchaseOrder:
        po = PurchaseOrderService.create_purchase_order(validated_data)

        return po


class PurchaseOrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Purchase Orders and Details"""

    order_details = PurchaseOrderDetailSerializer(many=True, required=False)

    class Meta:
        model = PurchaseOrder
        fields = [
            "purchase_order_number",
            "status",
            "supplier_name",
            "total_qty",
            "total_amount",
            "invoice_number",
            "delivery_date",
            "order_details",
        ]
        extra_kwargs = {
            "purchase_order_number": {"required": False},
        }

    def update(self, instance: PurchaseOrder, validated_data: dict) -> PurchaseOrder:
        details_data = validated_data.pop("order_details", None)

        # Update PO fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update details if provided
        if details_data is not None:
            for detail_data in details_data:
                detail_id = detail_data.get("id")
                if detail_id:
                    detail = instance.order_details.get(id=detail_id)
                    for attr, value in detail_data.items():
                        setattr(detail, attr, value)
                    detail.save()

        return instance


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
