from typing import Dict, List

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import ProductVariant, Warehouse
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from core.models import Company
from core.utils import is_valid_status_transition


class PurchaseOrderService:
    """
    Service for Purchase Order operations.
    Handles creation, updates, and inventory-related logic.
    """

    # Define allowed status transitions
    STATUS_TRANSITIONS: Dict[str, List[str]] = {
        PurchaseOrder.POStatus.DRAFT: [PurchaseOrder.POStatus.ORDERED],
        PurchaseOrder.POStatus.ORDERED: [
            PurchaseOrder.POStatus.SHIPPED,
            PurchaseOrder.POStatus.DRAFT,
        ],
        PurchaseOrder.POStatus.SHIPPED: [PurchaseOrder.POStatus.DELIVERED],
        PurchaseOrder.POStatus.DELIVERED: [PurchaseOrder.POStatus.COMPLETED],
        PurchaseOrder.POStatus.COMPLETED: [],
    }

    @transaction.atomic
    def create_purchase_order(self, data: dict) -> None:
        """
        Create a Purchase Order with nested order details.

        Args:
            data: Dictionary with PO fields and order_details array
                {
                    "purchase_order_number": "PO-001",
                    "warehouse_id": "...",
                    "company_id": "...",
                    "supplier_name": "Supplier ABC",
                    "total_qty": 100,
                    "total_amount": 10250000,
                    "order_details": [
                        {
                            "product_variant_id": "...",
                            "ordered_qty": 50,
                            "unit_price_base": 220000,
                        }
                    ]
                }

        Returns:
            Created PurchaseOrder instance
        """
        # Extract nested details
        details_data = data.pop("order_details", [])
        warehouse_id = data.pop("warehouse_id")
        company_id = data.pop("company_id")

        # Validate required data
        if not details_data:
            raise ValidationError("At least one order detail is required")

        # Get ForeignKey objects
        warehouse = Warehouse.objects.get(id=warehouse_id)
        company = Company.objects.get(id=company_id)

        # Create the PurchaseOrder with DRAFT status by default
        data.setdefault("status", PurchaseOrder.POStatus.DRAFT)
        po = PurchaseOrder.objects.create(warehouse=warehouse, company=company, **data)

        # Create related details
        for detail_data in details_data:
            product_variant_id = detail_data.pop("product_variant_id")
            product_variant = ProductVariant.objects.get(id=product_variant_id)
            PurchaseOrderDetail.objects.create(
                purchase_order=po, product_variant=product_variant, company=company, **detail_data
            )

    @staticmethod
    def update_purchase_order(po: PurchaseOrder, data: dict) -> PurchaseOrder:
        """
        Update a Purchase Order and its details.
        Validates status changes based on business rules.

        Args:
            po: PurchaseOrder instance to update
            data: Dictionary with fields to update
                {
                    "status": "ORDERED",
                    "supplier_name": "New Supplier",
                    "total_qty": 150,
                    "order_details": [
                        {"id": "...", "ordered_qty": 75}
                    ]
                }

        Returns:
            Updated PurchaseOrder instance
        """
        # Validate status change if provided
        if "status" in data:
            new_status = data["status"]
            PurchaseOrderService._validate_status_transition(po, new_status)

        # Extract order_details for separate handling
        details_data = data.pop("order_details", None)

        # Update PO fields
        for attr, value in data.items():
            if attr != "id":  # Skip id field
                setattr(po, attr, value)
        po.save()

        # Update details if provided
        if details_data is not None:
            for detail_data in details_data:
                detail_id = detail_data.get("id")
                if detail_id:
                    try:
                        detail = po.order_details.get(id=detail_id)
                        for attr, value in detail_data.items():
                            if attr != "id":
                                setattr(detail, attr, value)
                        detail.save()
                    except PurchaseOrderDetail.DoesNotExist:
                        raise ValidationError(f"Detail with id {detail_id} not found")

        return po

    @staticmethod
    def _validate_status_transition(po: PurchaseOrder, new_status: str) -> None:
        """
        Validate status transition is allowed.

        Allowed transitions:
        - DRAFT → ORDERED
        - ORDERED → SHIPPED, DRAFT
        - SHIPPED → DELIVERED
        - DELIVERED → COMPLETED
        - COMPLETED → (no transitions)
        """
        old_status = po.status

        # Check if transition is valid
        if not is_valid_status_transition(
            old_status, new_status, PurchaseOrderService.STATUS_TRANSITIONS
        ):
            allowed = PurchaseOrderService.STATUS_TRANSITIONS.get(old_status, [])
            raise ValidationError(
                f"Cannot transition from {old_status} to {new_status}. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}"
            )

        # Add business logic validation for specific transitions
        if (
            old_status == PurchaseOrder.POStatus.DRAFT
            and new_status == PurchaseOrder.POStatus.ORDERED
        ):
            if not po.purchase_order_invoice_file:
                raise ValidationError("please upload the invoice file")

        if (
            old_status == PurchaseOrder.POStatus.ORDERED
            and new_status == PurchaseOrder.POStatus.SHIPPED
        ):
            if not po.supplier_name:
                raise ValidationError("Supplier name is required before shipping")

    @staticmethod
    def handle_delivery_update(po: PurchaseOrder, details_data: list) -> None:
        """
        Handle inventory updates when delivery is received.
        Base template for inventory logic.

        Args:
            po: PurchaseOrder instance
            details_data: List of detail updates with received quantities
                [
                    {"id": "...", "received_qty": 50}
                ]
        """
        for detail_data in details_data:
            detail_id = detail_data.get("id")
            received_qty = detail_data.get("received_qty")

            if detail_id and received_qty:
                try:
                    detail = po.order_details.get(id=detail_id)
                    detail.received_qty = received_qty
                    detail.save()

                    # TODO: Update inventory/warehouse stock
                    # warehouse = po.warehouse
                    # warehouse.update_stock(
                    #     product_variant=detail.product_variant,
                    #     quantity_added=received_qty
                    # )

                except PurchaseOrderDetail.DoesNotExist:
                    raise ValidationError(f"Detail with id {detail_id} not found")
