from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import ProductVariant, ProductVariantWarehouse, StockMovement


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
        movement_type: str,
        data: list[dict],
        map_product_variant: dict,
        map_product_warehouse: dict,
        reference_number: Optional[str] = None,
    ) -> None:
        """Create stock movement records.

        Args:
            warehouse_id: The warehouse ID
            movement_type: Type of movement (PURCHASE, INBOUND, etc.)
            data: List of dicts with product_variant_id, qty, note
            map_product_variant: Dict mapping id -> ProductVariant. If not provided, will query internally.
            map_product_warehouse: Dict mapping product_variant_id -> ProductVariantWarehouse. If not provided, will query internally.
            reference_number: Optional reference (e.g., PO number)

        Note:
            For better performance, provide map_product_variant and map_product_warehouse
            when calling from purchasing service (ORDERED status).
        """
        if not map_product_variant and not map_product_warehouse:
            return

        stock_movements: list[StockMovement] = []
        for item in data:
            balance_after = 0
            product_variant_id = item.get("product_variant_id")
            pv = map_product_variant.get(product_variant_id)
            if not pv:
                raise ValidationError(f"ProductVariant with id {product_variant_id} not found")
            pvw = map_product_warehouse.get(product_variant_id)

            qty = item.get("qty", 0)
            if movement_type == StockMovement.MovementType.PURCHASE:
                field_change = "incoming_qty"
                balance_before = pvw.incoming_qty if pvw else 0
                balance_after = balance_before + qty

            if movement_type == StockMovement.MovementType.INBOUND:
                field_change = "available_qty"
                balance_before = pvw.available_qty if pvw else 0
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
    def update_inventory_on_po_ordered(
        self,
        warehouse_id: int,
        data: list[dict],
        map_product_variant: dict,
        map_product_warehouse: dict,
    ) -> None:
        """Update inventory when PO status becomes ORDERED (PURCHASE movement).

        This handles:
        - ProductVariantWarehouse.incoming_qty (per warehouse)
        - ProductVariant.total_incoming_qty (global)

        Args:
            warehouse_id: The warehouse to update
            data: List of dicts with product_variant_id and qty
            map_product_variant: Dict mapping id -> ProductVariant.
            map_product_warehouse: Dict mapping product_variant_id -> ProductVariantWarehouse.

        Note:
            Call record_multiple_stock_movements() separately to create movement records.
            For better performance, provide pre-fetched maps when calling from purchasing service.
        """
        new_pvws: list[ProductVariantWarehouse] = []
        update_pvws: list[ProductVariantWarehouse] = []
        update_pv: list[ProductVariant] = []
        update_fields_pvw = set()
        update_fields_pv = set()

        for item in data:
            product_variant_id = item.get("product_variant_id")
            qty = item.get("qty", 0)

            pv = map_product_variant.get(product_variant_id)
            if not pv:
                raise ValidationError(f"ProductVariant with id {product_variant_id} not found")

            pvw = map_product_warehouse.get(product_variant_id)
            if not pvw:
                pvw = ProductVariantWarehouse(
                    product_variant=pv,
                    warehouse_id=warehouse_id,
                    incoming_qty=0,
                    physical_qty=0,
                )
                new_pvws.append(pvw)
            else:
                update_pvws.append(pvw)

            pvw.incoming_qty += qty
            pvw.udate = timezone.now()
            update_fields_pvw.add("incoming_qty")
            update_fields_pvw.add("udate")

            pv.total_incoming_qty += qty
            pv.udate = timezone.now()
            update_fields_pv.add("total_incoming_qty")
            update_fields_pv.add("udate")
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
