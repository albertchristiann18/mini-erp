from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django_ulid.models import ULIDField

from apps.inventory.models import ProductVariant, ProductVariantWarehouse, StockMovement, Warehouse
from apps.inventory.services.inventory_service import InventoryService
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from core.models import Company


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
        """Update a Purchase Order and its details.

        Validations are handled by PurchaseOrderUpdateSerializer before this method is called.
        File compression is handled in the serializer's validate_<field> methods.
        """
        old_status = po.status
        new_status = data.get("status")

        if new_status == PurchaseOrder.POStatus.DELIVERED and not data.get("delivery_date"):
            data["delivery_date"] = timezone.now()

        inventory_data = []
        if new_status == PurchaseOrder.POStatus.ORDERED:
            for detail in po.order_details.all():
                inventory_data.append(
                    {
                        "product_variant_id": detail.product_variant.id,
                        "ordered_qty": detail.ordered_qty,
                        "note": f"Stock movement for PO {po.purchase_order_number} purchase",
                    }
                )

        elif new_status == PurchaseOrder.POStatus.DELIVERED:
            for item in data.get("order_details", []):
                receive_date_str = item.get("received_date")
                received_qty = item.get("received_qty", 0)
                ordered_qty = item.get("ordered_qty", 0)
                updated_qty = item.get("updated_qty", 0) or 0
                product_variant_id = item.get("product_variant_id")
                if not product_variant_id:
                    continue
                if not receive_date_str or not received_qty:
                    continue
                receive_date = datetime.fromisoformat(receive_date_str.replace("Z", "+00:00"))
                if receive_date and po.delivery_date and receive_date.date() < po.delivery_date:
                    continue

                inventory_data.append(
                    {
                        "product_variant_id": product_variant_id,
                        "ordered_qty": ordered_qty,
                        "received_qty": received_qty,
                        "updated_qty": updated_qty,
                        "unit_price_base": item.get("unit_price_base"),
                        "unit_price_foreign": item.get("unit_price_foreign"),
                        "discounted_unit_price_foreign": item.get("discounted_unit_price_foreign"),
                        "exchange_rate": po.exchange_rate,
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

        details_data = data.pop("order_details", None)

        updated_fields = ["udate"]
        for attr, value in data.items():
            if attr != "id":
                updated_fields.append(attr)
                setattr(po, attr, value)
        po.save(update_fields=updated_fields)

        if details_data is not None:
            self._update_order_details(po, details_data, old_status)

        self._recalculate_po_totals(po)

        return po

    def _update_order_details(
        self, po: PurchaseOrder, details_data: list, current_status: str
    ) -> None:
        """Handle order details update/create/delete."""
        ulid_field = ULIDField()
        existing_details = {}
        new_details: list[PurchaseOrderDetail] = []
        update_details: list[PurchaseOrderDetail] = []
        update_fields_set: set = set()
        existing_detail_ids: list = []

        for detail_data in details_data:
            if detail_id := detail_data.get("id"):
                converted_id = ulid_field.to_python(detail_id)
                existing_detail_ids.append(converted_id)

        existing_details_map = {}
        if existing_detail_ids:
            existing_details_map = {
                d.id: d for d in po.order_details.filter(id__in=existing_detail_ids)
            }

        for detail_data in details_data:
            detail_id = detail_data.get("id")
            if detail_id:
                converted_id = ulid_field.to_python(detail_id)
                detail = existing_details_map.get(converted_id)
                if not detail:
                    if current_status == PurchaseOrder.POStatus.DRAFT:
                        pass
                    else:
                        raise ValidationError(f"Detail with id {detail_id} not found")
                else:
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
                    product_variant_id = ulid_field.to_python(detail_data.get("product_variant_id"))
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

        if po.status == PurchaseOrder.POStatus.DRAFT:
            ids_to_keep = [d.id for d in update_details] + [d.id for d in new_details]
            po.order_details.exclude(id__in=ids_to_keep).delete()

        if update_details:
            update_fields_list = list(update_fields_set) + ["udate"]
            PurchaseOrderDetail.objects.bulk_update(
                update_details, update_fields_list, batch_size=100
            )

        if new_details:
            PurchaseOrderDetail.objects.bulk_create(new_details, batch_size=100)

    def _recalculate_po_totals(self, po: PurchaseOrder) -> None:
        """Recalculate PO totals based on order details and fee fields."""
        total_ordered_qty = 0
        total_received_qty = 0
        total_item_amount = 0

        for detail in po.order_details.all():
            total_ordered_qty += detail.ordered_qty or 0
            total_received_qty += detail.received_qty or 0
            total_item_amount += detail.discounted_total_price_base or 0

        exchange_rate = Decimal(str(po.exchange_rate or 0))
        commission_fee_pct = Decimal(str(po.commission_fee_pct or 0))
        delivery_fee = Decimal(str(po.delivery_fee or 0))
        shipping_fee_per_cbm = Decimal(str(po.shipping_fee_per_cbm or 0))
        cbm = Decimal(str(po.cbm or 0))

        commission_fee = int(round(commission_fee_pct * delivery_fee * exchange_rate))
        shipping_fee = int(round(shipping_fee_per_cbm * cbm))
        procure_amount = shipping_fee + commission_fee
        total_order_amount = total_item_amount + commission_fee
        total_amount = total_item_amount + commission_fee + shipping_fee

        update_fields = []
        if po.total_ordered_qty != total_ordered_qty:
            po.total_ordered_qty = total_ordered_qty
            update_fields.append("total_ordered_qty")
        if po.total_received_qty != total_received_qty:
            po.total_received_qty = total_received_qty
            update_fields.append("total_received_qty")
        if po.total_item_amount != total_item_amount:
            po.total_item_amount = total_item_amount
            update_fields.append("total_item_amount")
        if po.commission_fee != commission_fee:
            po.commission_fee = commission_fee
            update_fields.append("commission_fee")
        if po.shipping_fee != shipping_fee:
            po.shipping_fee = shipping_fee
            update_fields.append("shipping_fee")
        if po.procure_amount != procure_amount:
            po.procure_amount = procure_amount
            update_fields.append("procure_amount")
        if po.total_order_amount != total_order_amount:
            po.total_order_amount = total_order_amount
            update_fields.append("total_order_amount")
        if po.total_amount != total_amount:
            po.total_amount = total_amount
            update_fields.append("total_amount")

        if update_fields:
            update_fields.append("udate")
            po.save(update_fields=update_fields)
