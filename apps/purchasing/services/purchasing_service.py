from datetime import datetime
from typing import Dict, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import ProductVariant, ProductVariantWarehouse, StockMovement, Warehouse
from apps.inventory.services.inventory_service import InventoryService
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from core.models import Company
from core.utils import compress_pdf_file, is_valid_status_transition


class PurchaseOrderService:
    """
    Service for Purchase Order operations.
    Handles creation, updates, and inventory-related logic.
    """

    STATUS_TRANSITIONS: Dict[str, List[str]] = {
        PurchaseOrder.POStatus.DRAFT: [PurchaseOrder.POStatus.ORDERED],
        PurchaseOrder.POStatus.ORDERED: [
            PurchaseOrder.POStatus.SHIPPED,
        ],
        PurchaseOrder.POStatus.SHIPPED: [PurchaseOrder.POStatus.DELIVERED],
        PurchaseOrder.POStatus.DELIVERED: [PurchaseOrder.POStatus.COMPLETED],
        PurchaseOrder.POStatus.COMPLETED: [],
    }

    def _handle_status_inventory(
        self,
        po: PurchaseOrder,
        new_status: str,
        data: list[dict],
    ) -> None:
        """Handle inventory update for ORDER or DELIVERED status.

        For ORDERED (PURCHASE movement):
        - ProductVariantWarehouse.incoming_qty += qty
        - ProductVariant.total_incoming_qty += qty

        For DELIVERED (INBOUND movement):
        - ProductVariantWarehouse.incoming_qty -= min(ordered_qty, received_qty)
        - ProductVariantWarehouse.physical_qty += received_qty
        - ProductVariant.total_incoming_qty -= min(ordered_qty, received_qty)
        - ProductVariant.total_available_qty += received_qty

        Args:
            po: PurchaseOrder instance
            new_status: Target status (ORDERED or DELIVERED)
            data: List of item dicts with product_variant_id, qty (for ORDERED) or ordered_qty, received_qty (for DELIVERED)
        """
        if not data:
            return

        movement_type = (
            StockMovement.MovementType.PURCHASE
            if new_status == PurchaseOrder.POStatus.ORDERED
            else StockMovement.MovementType.INBOUND
        )

        product_variant_ids = [item.get("product_variant_id") for item in data]
        product_variants = list(
            ProductVariant.objects.select_for_update().filter(id__in=product_variant_ids)
        )
        product_variant_warehouses = list(
            ProductVariantWarehouse.objects.select_for_update().filter(
                product_variant__in=product_variants, warehouse_id=po.warehouse.id
            )
        )

        map_product_variant = {pv.id: pv for pv in product_variants}
        map_product_warehouse = {pvw.product_variant.id: pvw for pvw in product_variant_warehouses}

        reference_number = (
            po.purchase_order_number
            if new_status == PurchaseOrder.POStatus.ORDERED
            else po.delivery_order_number
        )

        inventory_service = InventoryService()
        inventory_service.record_multiple_stock_movements(
            warehouse_id=po.warehouse.id,
            movement_type=movement_type,
            data=data,
            reference_number=reference_number,
            map_product_variant=map_product_variant,
            map_product_warehouse=map_product_warehouse,
        )

        if new_status == PurchaseOrder.POStatus.ORDERED:
            inventory_service.update_inventory_on_po_ordered(
                warehouse_id=po.warehouse.id,
                data=data,
                map_product_variant=map_product_variant,
                map_product_warehouse=map_product_warehouse,
            )
            for detail in po.order_details.all():
                detail.updated_qty = detail.ordered_qty
                detail.save(update_fields=["updated_qty", "udate"])
        elif new_status == PurchaseOrder.POStatus.DELIVERED:
            inventory_service.update_inventory_on_po_delivered(
                warehouse_id=po.warehouse.id,
                data=data,
                map_product_variant=map_product_variant,
                map_product_warehouse=map_product_warehouse,
            )
            for item in data:
                detail = po.order_details.get(id=item.get("id"))
                received_qty = item.get("received_qty", 0)
                detail.updated_qty = detail.updated_qty + received_qty
                detail.save(update_fields=["updated_qty", "udate"])

    @transaction.atomic
    def create_purchase_order(self, data: dict) -> None:
        """Create a Purchase Order with nested order details."""
        details_data = data.pop("order_details", [])
        warehouse_id = data.pop("warehouse_id")
        company_id = data.pop("company_id")

        if not details_data:
            raise ValidationError("At least one order detail is required")

        warehouse = Warehouse.objects.get(id=warehouse_id)
        company = Company.objects.get(id=company_id)

        data.setdefault("status", PurchaseOrder.POStatus.DRAFT)
        po = PurchaseOrder.objects.create(warehouse=warehouse, company=company, **data)

        for detail_data in details_data:
            product_variant_id = detail_data.pop("product_variant_id")
            product_variant = ProductVariant.objects.get(id=product_variant_id)
            PurchaseOrderDetail.objects.create(
                purchase_order=po, product_variant=product_variant, company=company, **detail_data
            )

    @transaction.atomic
    def update_purchase_order(self, po: PurchaseOrder, data: dict) -> PurchaseOrder:
        """Update a Purchase Order and its details."""
        purchase_order_invoice_file = data.get("purchase_order_invoice_file")
        delivery_order_number = data.get("delivery_order_number")
        delivery_order_file = data.get("delivery_order_file")
        delivery_order_invoice_file = data.get("delivery_order_invoice_file")

        if "status" in data:
            old_status = po.status
            new_status = data["status"]

            if not is_valid_status_transition(
                old_status, new_status, PurchaseOrderService.STATUS_TRANSITIONS
            ):
                allowed = PurchaseOrderService.STATUS_TRANSITIONS.get(old_status, [])
                raise ValidationError(
                    f"Cannot transition from {old_status} to {new_status}. "
                    f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}"
                )

            if (
                old_status == PurchaseOrder.POStatus.DRAFT
                and new_status == PurchaseOrder.POStatus.ORDERED
                and (not po.purchase_order_invoice_file and purchase_order_invoice_file is None)
            ):
                raise ValidationError("please upload the invoice file")
            elif (
                old_status == PurchaseOrder.POStatus.ORDERED
                and new_status == PurchaseOrder.POStatus.SHIPPED
            ):
                if not po.delivery_order_number and delivery_order_number is None:
                    raise ValidationError("please provide the delivery order number")
                elif not po.delivery_order_file and delivery_order_file is None:
                    raise ValidationError("please upload the delivery order file")
            elif (
                old_status == PurchaseOrder.POStatus.SHIPPED
                and new_status == PurchaseOrder.POStatus.DELIVERED
            ):
                if not po.delivery_order_invoice_file and delivery_order_invoice_file is None:
                    raise ValidationError("please upload the delivery order invoice file")

                if not data.get("delivery_date"):
                    po.delivery_date = timezone.now()

            if (
                new_status == PurchaseOrder.POStatus.ORDERED
                and old_status != PurchaseOrder.POStatus.ORDERED
            ):
                stored_data = []
                for detail in po.order_details.all():
                    stored_data.append(
                        {
                            "product_variant_id": str(detail.product_variant.id),
                            "qty": detail.ordered_qty,
                            "note": f"Stock movement for PO {po.purchase_order_number} purchase",
                        }
                    )
                self._handle_status_inventory(po, new_status, stored_data)

            if new_status == PurchaseOrder.POStatus.DELIVERED:
                valid_items = []
                for item in data.get("order_details", []):
                    receive_date_str = item.get("received_date")
                    received_qty = item.get("received_qty", 0)
                    ordered_qty = item.get("ordered_qty", 0)
                    if not receive_date_str or not received_qty:
                        continue
                    receive_date = datetime.fromisoformat(receive_date_str.replace("Z", "+00:00"))
                    if receive_date and ordered_qty == received_qty:
                        continue
                    if receive_date and po.delivery_date and receive_date.date() < po.delivery_date:
                        continue

                    valid_items.append(
                        {
                            "id": item.get("id"),
                            "product_variant_id": item.get("product_variant_id"),
                            "ordered_qty": ordered_qty,
                            "received_qty": received_qty,
                            "note": f"Stock movement for PO {po.purchase_order_number} inbound",
                        }
                    )

                if valid_items:
                    self._handle_status_inventory(po, new_status, valid_items)

        if purchase_order_invoice_file:
            po_invoice_compressed_file = compress_pdf_file(purchase_order_invoice_file)
            data["purchase_order_invoice_file"] = po_invoice_compressed_file

        if delivery_order_file:
            do_compressed_file = compress_pdf_file(delivery_order_file)
            data["delivery_order_file"] = do_compressed_file

        if delivery_order_invoice_file:
            do_invoice_compressed_file = compress_pdf_file(delivery_order_invoice_file)
            data["delivery_order_invoice_file"] = do_invoice_compressed_file

        details_data = data.pop("order_details", None)

        updated_fields = ["udate"]
        for attr, value in data.items():
            if attr != "id":
                updated_fields.append(attr)
                setattr(po, attr, value)
        po.save(update_fields=updated_fields)

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
