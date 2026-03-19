from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django_ulid.models import ULIDField

from apps.inventory.models import (
    ProductCogs,
    ProductVariant,
    ProductVariantWarehouse,
    StockMovement,
)
from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail


class InventoryService:
    @transaction.atomic
    def record_single_stock_movement(
        self,
        variant_id: int,
        warehouse_id: int,
        qty: int,  # need to be absolute value (not negative)
        movement_type: str,
        reference_number: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """
        Args:
            variant_id (int): product_variant_id
            warehouse (Warehouse): the warehouse where this movement happens
            qty (int): quantity
            reference_number (str, optional): reference number can refer to po_number, or invoice_number etc.
            note (str, optional): notes / remarks for each movement

        Notes:
            - for movement_type = ADJUSTMENT, qty can be inpputed positive or negative
            - for movement_type = TRANSFER, handled outside this method
        """
        if movement_type == StockMovement.MovementType.TRANSFER:
            return  # skip transfer type

        variant = ProductVariant.objects.select_for_update().get(id=variant_id)
        pvw = (
            ProductVariantWarehouse.objects.select_for_update()
            .filter(product_variant=variant, warehouse_id=warehouse_id)
            .last()
        )
        if not pvw:
            pvw = ProductVariantWarehouse.objects.create(
                product_variant=variant,
                warehouse_id=warehouse_id,
            )

        balance_before = variant.total_available_qty

        if movement_type == StockMovement.MovementType.PURCHASE:
            pvw.incoming_qty += qty
            pvw.save(update_fields=["incoming_qty"])
            return
        elif movement_type == StockMovement.MovementType.OUTBOUND:
            pvw.physical_qty -= qty
            variant.total_available_qty -= qty
        else:
            pvw.physical_qty += qty
            variant.total_available_qty += qty

        StockMovement.objects.create(
            product_variant=variant,
            warehouse_id=warehouse_id,
            quantity=qty,
            movement_type=movement_type,
            balance_before=balance_before,
            balance_after=variant.total_available_qty,
            reference_number=reference_number,
            note=note,
        )

        pvw.save(update_fields=["physical_qty"])
        variant.save(update_fields=["total_available_qty"])

        return

    @transaction.atomic
    def record_multiple_stock_movements(
        self,
        warehouse_id: int,
        data: list[dict],
        map_product_variant: dict,
        reference_number: Optional[str] = None,
        movement_type: Optional[str] = None,
    ) -> None:
        """Create stock movement records.

        Args:
            warehouse_id: The warehouse ID
            data: List of dicts with product_variant_id, qty, note, field_change, qty_before
            map_product_variant: Dict mapping id -> ProductVariant.
            reference_number: Optional reference (e.g., PO number)
            movement_type: Type of movement (PURCHASE, INBOUND, etc.).
        """
        stock_movements: list[StockMovement] = []
        for item in data:
            product_variant_id = item.get("product_variant_id")
            pv = map_product_variant.get(product_variant_id)
            if not pv:
                raise ValidationError(f"ProductVariant with id {product_variant_id} not found")

            qty = item.get("qty", 0)
            field_change = item.get("field_change")
            balance_before = item.get("qty_before", 0)
            balance_after = balance_before + qty

            stock_movements.append(
                StockMovement(
                    product_variant_id=product_variant_id,
                    warehouse_id=warehouse_id,
                    quantity=qty,
                    field_change=field_change,
                    movement_type=movement_type,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    reference_number=reference_number,
                    note=item.get("note"),
                )
            )

        StockMovement.objects.bulk_create(stock_movements, batch_size=100)

    @transaction.atomic
    def update_inventory_on_po(
        self,
        po: object,
        new_status: str,
        data: list[dict],
    ) -> None:
        """Update inventory when PO status changes.

        For PURCHASE (ORDERED):
        - ProductVariantWarehouse.incoming_qty += ordered_qty
        - ProductVariant.total_incoming_qty += ordered_qty

        For INBOUND (DELIVERED) - first time (already_processed == 0):
        - ProductVariantWarehouse.incoming_qty -= ordered_qty
        - ProductVariantWarehouse.physical_qty += received_qty
        - ProductVariant.total_incoming_qty -= ordered_qty
        - ProductVariant.total_available_qty += received_qty

        For INBOUND (DELIVERED) - subsequent (already_processed > 0):
        - ProductVariantWarehouse.physical_qty += qty_diff
        - ProductVariant.total_available_qty += qty_diff

        Args:
            po: PurchaseOrder instance (must have warehouse.id attribute)
            new_status: Target status (ORDERED or DELIVERED)
            data: List of dicts with product_variant_id, ordered_qty, received_qty, updated_qty
        """
        if not data:
            return

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

        movements = []

        if new_status == PurchaseOrder.POStatus.ORDERED:
            movement_type = StockMovement.MovementType.PURCHASE
            for item in data:
                pv_id = item.get("product_variant_id")
                pvw = map_product_warehouse.get(pv_id)
                movements.append(
                    {
                        "product_variant_id": pv_id,
                        "qty": item.get("ordered_qty", 0),
                        "field_change": "incoming_qty",
                        "qty_before": pvw.incoming_qty if pvw else 0,
                        "note": item.get("note"),
                    }
                )

        elif new_status == PurchaseOrder.POStatus.DELIVERED:
            movement_type = StockMovement.MovementType.INBOUND
            for item in data:
                pv_id = item.get("product_variant_id")
                pvw = map_product_warehouse.get(pv_id)
                ordered_qty = item.get("ordered_qty", 0)
                received_qty = item.get("received_qty", 0)
                already_processed = item.get("updated_qty", 0) or 0

                if already_processed == 0:
                    movements.append(
                        {
                            "product_variant_id": pv_id,
                            "qty": ordered_qty,
                            "field_change": "incoming_qty",
                            "qty_before": pvw.incoming_qty if pvw else 0,
                            "note": item.get("note"),
                        }
                    )
                    movements.append(
                        {
                            "product_variant_id": pv_id,
                            "qty": received_qty,
                            "field_change": "physical_qty",
                            "qty_before": pvw.physical_qty if pvw else 0,
                            "note": item.get("note"),
                        }
                    )
                else:
                    qty_diff = received_qty - already_processed
                    if qty_diff != 0:
                        movements.append(
                            {
                                "product_variant_id": pv_id,
                                "qty": qty_diff,
                                "field_change": "physical_qty",
                                "qty_before": pvw.physical_qty if pvw else 0,
                                "note": item.get("note"),
                            }
                        )

        if movements:
            self.record_multiple_stock_movements(
                warehouse_id=po.warehouse.id,
                data=movements,
                map_product_variant=map_product_variant,
                reference_number=po.purchase_order_number,
                movement_type=movement_type,
            )

        new_pvws: list[ProductVariantWarehouse] = []
        update_pvws: list[ProductVariantWarehouse] = []
        update_pv: list[ProductVariant] = []
        update_fields_pvw = set()
        update_fields_pv = set()

        create_cogs_records: list[ProductCogs] = []
        update_cogs_records: list[ProductCogs] = []
        existing_cogs_map: dict = {}

        if new_status == PurchaseOrder.POStatus.DELIVERED:
            detail_ids = [item.get("detail_id") for item in data if item.get("detail_id")]
            if detail_ids:
                existing_cogs_map = {
                    cogs.purchase_order_detail_id: cogs
                    for cogs in ProductCogs.objects.filter(purchase_order_detail_id__in=detail_ids)
                }

        for item in data:
            product_variant_id = item.get("product_variant_id")
            detail_id = item.get("detail_id")

            pv = map_product_variant.get(product_variant_id)
            if not pv:
                raise ValidationError(f"ProductVariant with id {product_variant_id} not found")

            pvw = map_product_warehouse.get(product_variant_id)
            created_pvw = False
            if not pvw:
                pvw = ProductVariantWarehouse(
                    product_variant=pv,
                    warehouse_id=po.warehouse.id,
                    incoming_qty=0,
                    physical_qty=0,
                )
                new_pvws.append(pvw)
                created_pvw = True
            else:
                update_pvws.append(pvw)

            if movement_type == StockMovement.MovementType.PURCHASE:
                ordered_qty = item.get("ordered_qty", 0)
                pvw.incoming_qty += ordered_qty
                update_fields_pvw.add("incoming_qty")

                pv.total_incoming_qty += ordered_qty
                update_fields_pv.add("total_incoming_qty")

            elif movement_type == StockMovement.MovementType.INBOUND:
                ordered_qty = item.get("ordered_qty", 0)
                received_qty = item.get("received_qty", 0)
                already_processed = item.get("updated_qty", 0) or 0

                if already_processed == 0:
                    pvw.incoming_qty -= ordered_qty
                    pvw.physical_qty += received_qty
                    update_fields_pvw.update(["incoming_qty", "physical_qty"])

                    pv.total_incoming_qty -= ordered_qty
                    pv.total_available_qty += received_qty
                    update_fields_pv.update(["total_incoming_qty", "total_available_qty"])

                    if received_qty > 0 and detail_id:
                        unit_price_base = item.get("unit_price_base", 0) or 0
                        unit_price_foreign = item.get("unit_price_foreign", 0) or 0
                        exchange_rate = item.get("exchange_rate", 1) or 1
                        received_date = item.get("received_date") or timezone.now().date()

                        if unit_price_foreign and exchange_rate and exchange_rate != 1:
                            price_rmb = unit_price_foreign
                            cogs_amount = int(
                                float(unit_price_foreign) * float(exchange_rate) * received_qty
                            )
                        else:
                            price_rmb = unit_price_base
                            cogs_amount = unit_price_base * received_qty

                        ulid_field = ULIDField()
                        converted_detail_id = ulid_field.to_python(detail_id)

                        create_cogs_records.append(
                            ProductCogs(
                                product_variant=pv,
                                warehouse=po.warehouse,
                                purchase_order_detail_id=converted_detail_id,
                                purchase_date=received_date,
                                price_rmb=price_rmb,
                                exchange_rate=exchange_rate,
                                cogs_amount=cogs_amount,
                                original_qty=received_qty,
                                remaining_qty=received_qty,
                            )
                        )
                else:
                    qty_diff = received_qty - already_processed
                    if qty_diff != 0:
                        pvw.physical_qty += qty_diff
                        update_fields_pvw.add("physical_qty")

                        pv.total_available_qty += qty_diff
                        update_fields_pv.add("total_available_qty")

                        incoming_adjustment = already_processed - received_qty
                        if incoming_adjustment > 0:
                            pvw.incoming_qty += incoming_adjustment
                            update_fields_pvw.add("incoming_qty")

                            pv.total_incoming_qty += incoming_adjustment
                            update_fields_pv.add("total_incoming_qty")

                        if detail_id:
                            ulid_field = ULIDField()
                            converted_detail_id = ulid_field.to_python(detail_id)
                            existing_cogs = existing_cogs_map.get(converted_detail_id)
                            if existing_cogs:
                                existing_cogs.original_qty = received_qty
                                if qty_diff > 0:
                                    existing_cogs.remaining_qty += qty_diff
                                unit_price_base = item.get("unit_price_base", 0) or 0
                                existing_cogs.cogs_amount = (
                                    unit_price_base * existing_cogs.remaining_qty
                                )
                                update_cogs_records.append(existing_cogs)

            pvw.udate = timezone.now()
            pv.udate = timezone.now()
            update_fields_pvw.add("udate")
            update_fields_pv.add("udate")
            if created_pvw:
                update_pvws.append(pvw)
            update_pv.append(pv)

        ProductVariantWarehouse.objects.bulk_create(new_pvws, batch_size=100)
        if update_pvws:
            ProductVariantWarehouse.objects.bulk_update(
                update_pvws, fields=list(update_fields_pvw), batch_size=100
            )
        if update_pv:
            ProductVariant.objects.bulk_update(
                update_pv, fields=list(update_fields_pv), batch_size=100
            )

        if create_cogs_records:
            ProductCogs.objects.bulk_create(create_cogs_records, batch_size=100)

        if update_cogs_records:
            ProductCogs.objects.bulk_update(
                update_cogs_records,
                fields=["original_qty", "remaining_qty", "cogs_amount"],
                batch_size=100,
            )
