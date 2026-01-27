from typing import Optional

from django.db import transaction

from apps.inventory.models import ProductVariant, ProductVariantWarehouse, StockMovement, Warehouse


class InventoryService:
    @transaction.atomic
    def record_single_stock_movement(
        self,
        variant_id: int,
        warehouse: Warehouse,
        qty: int,  # need to be absolute value (not negative)
        movement_type: str,
        reference_number: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """
        Args:
            variant_id (int): _description_
            warehouse (Warehouse): _description_
            qty (int): _description_
            reference_number (str, optional): _description_. Defaults to None.
            note (str, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_

        Notes:
            - for movement_type = ADJUSTMENT, qty can be inpputed positive or negative
            - for movement_type = TRANSFER, handled outside this method
        """
        if movement_type == StockMovement.MovementType.TRANSFER:
            return  # skip transfer type

        variant = ProductVariant.objects.select_for_update().get(id=variant_id)
        pvw = (
            ProductVariantWarehouse.objects.select_for_update()
            .filter(product_variant=variant, warehouse=warehouse)
            .last()
        )
        if not pvw:
            pvw = ProductVariantWarehouse.objects.create(
                product_variant=variant,
                warehouse=warehouse,
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
            warehouse=warehouse,
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
