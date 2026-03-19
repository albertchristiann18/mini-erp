from datetime import datetime
from typing import Dict, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django_ulid.models import ULIDField

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

    @transaction.atomic
    def create_purchase_order(self, data: dict) -> PurchaseOrder:
        """Create a Purchase Order with nested order details."""
        details_data = data.pop("order_details", [])
        warehouse_id = data.pop("warehouse_id")
        company_id = data.pop("company_id")

        warehouse = Warehouse.objects.get(id=warehouse_id)
        company = Company.objects.get(id=company_id)

        data.setdefault("status", PurchaseOrder.POStatus.DRAFT)
        po = PurchaseOrder.objects.create(warehouse=warehouse, company=company, **data)

        if details_data:
            order_details = []
            for detail_data in details_data:
                product_variant_id = detail_data.pop("product_variant_id")
                order_details.append(
                    PurchaseOrderDetail(
                        purchase_order=po,
                        product_variant_id=product_variant_id,
                        company=company,
                        **detail_data,
                    )
                )

            PurchaseOrderDetail.objects.bulk_create(order_details, batch_size=100)

        return po

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

            inventory_data = []

            if (
                new_status == PurchaseOrder.POStatus.ORDERED
                and old_status != PurchaseOrder.POStatus.ORDERED
            ):
                inventory_data = []
                for detail in po.order_details.all():
                    inventory_data.append(
                        {
                            "product_variant_id": detail.product_variant.id,
                            "ordered_qty": detail.ordered_qty,
                            "note": f"Stock movement for PO {po.purchase_order_number} purchase",
                        }
                    )

            elif new_status == PurchaseOrder.POStatus.DELIVERED:
                inventory_data = []
                for item in data.get("order_details", []):
                    receive_date_str = item.get("received_date")
                    received_qty = item.get("received_qty", 0)
                    ordered_qty = item.get("ordered_qty", 0)
                    updated_qty = item.get("updated_qty", 0) or 0
                    detail_id = item.get("id")
                    if not detail_id:
                        continue
                    if not receive_date_str or not received_qty:
                        continue
                    receive_date = datetime.fromisoformat(receive_date_str.replace("Z", "+00:00"))
                    if receive_date and ordered_qty == received_qty:
                        continue
                    if receive_date and po.delivery_date and receive_date.date() < po.delivery_date:
                        continue

                    inventory_data.append(
                        {
                            "detail_id": detail_id,
                            "product_variant_id": item.get("product_variant_id"),
                            "ordered_qty": ordered_qty,
                            "received_qty": received_qty,
                            "updated_qty": updated_qty,
                            "unit_price_base": item.get("unit_price_base"),
                            "unit_price_foreign": item.get("unit_price_foreign"),
                            "exchange_rate": po.exchange_rate,
                            "received_date": receive_date.date() if receive_date else None,
                            "note": f"Stock movement for PO {po.purchase_order_number} inbound",
                        }
                    )

            if inventory_data:
                inventory_service = InventoryService()
                inventory_service.update_inventory_on_po(
                    po=po,
                    new_status=new_status,
                    data=inventory_data,
                )

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
            ulid_field = ULIDField()
            current_status = po.status
            existing_details = {}
            new_details: list[PurchaseOrderDetail] = []
            update_details: list[PurchaseOrderDetail] = []
            update_fields_set: set = set()

            detail_ids_to_update = []
            for detail_data in details_data:
                detail_id = detail_data.get("id")
                if detail_id:
                    converted_id = ulid_field.to_python(detail_id)
                    detail_ids_to_update.append(converted_id)

            if detail_ids_to_update:
                existing_details = {
                    d.id: d for d in po.order_details.filter(id__in=detail_ids_to_update)
                }

            for detail_data in details_data:
                detail_id = detail_data.get("id")
                if detail_id:
                    converted_id = ulid_field.to_python(detail_id)
                    detail = existing_details.get(converted_id)
                    if not detail:
                        raise ValidationError(f"Detail with id {detail_id} not found")

                    is_delivered = current_status == PurchaseOrder.POStatus.DELIVERED
                    for attr, value in detail_data.items():
                        if attr == "id":
                            continue
                        if is_delivered and attr in ("updated_qty", "received_qty"):
                            continue
                        setattr(detail, attr, value)
                        update_fields_set.add(attr)

                    if is_delivered:
                        detail.updated_qty = detail_data.get("received_qty", 0)
                        detail.received_qty = detail_data.get("received_qty", 0)
                        update_fields_set.update(["updated_qty", "received_qty"])

                    update_details.append(detail)
                else:
                    if po.status == PurchaseOrder.POStatus.DRAFT:
                        product_variant_id = ulid_field.to_python(
                            detail_data.get("product_variant_id")
                        )
                        detail_data_copy = {
                            k: v for k, v in detail_data.items() if k != "product_variant_id"
                        }
                        detail = PurchaseOrderDetail(
                            purchase_order=po,
                            product_variant_id=product_variant_id,
                            company=po.company,
                            **detail_data_copy,
                        )
                        new_details.append(detail)

            if update_details:
                update_fields_list = list(update_fields_set) + ["udate"]
                PurchaseOrderDetail.objects.bulk_update(
                    update_details, update_fields_list, batch_size=100
                )

            if new_details:
                PurchaseOrderDetail.objects.bulk_create(new_details, batch_size=100)

            if po.status == PurchaseOrder.POStatus.DRAFT:
                po.order_details.exclude(id__in=detail_ids_to_update).delete()

        return po
