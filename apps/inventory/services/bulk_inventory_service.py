from django.db import transaction

from apps.inventory.models import ProductVariantWarehouse, StockMovement


class BulkInventoryService:
    @staticmethod
    @transaction.atomic
    def bulk_update(updates: list[dict]) -> dict:
        results = []
        errors = []

        for update in updates:
            variant_id = update.get("variant_id")
            warehouse_id = update.get("warehouse_id")
            qty = int(update.get("qty", 0))
            update_type = update.get("type", "replace")

            try:
                pvw = ProductVariantWarehouse.objects.select_for_update().get(
                    product_variant_id=variant_id,
                    warehouse_id=warehouse_id,
                )
                balance_before = pvw.physical_qty

                if update_type == "replace":
                    new_qty = qty
                elif update_type == "add":
                    new_qty = pvw.physical_qty + qty
                elif update_type == "min":
                    new_qty = pvw.physical_qty - qty
                    if new_qty < 0:
                        errors.append(
                            {
                                "variant_id": variant_id,
                                "warehouse_id": warehouse_id,
                                "error": f"Insufficient stock. Current: {pvw.physical_qty}, requested reduction: {qty}",
                            }
                        )
                        continue
                else:
                    errors.append(
                        {
                            "variant_id": variant_id,
                            "warehouse_id": warehouse_id,
                            "error": f"Invalid type: {update_type}",
                        }
                    )
                    continue

                pvw.physical_qty = new_qty
                pvw.save(update_fields=["physical_qty"])

                variant = pvw.product_variant
                total_available = sum(
                    w.physical_qty - w.checkout_qty for w in variant.warehouse_stocks.all()
                )
                variant.total_available_qty = total_available
                variant.save(update_fields=["total_available_qty"])

                StockMovement.objects.create(
                    company=pvw.company,
                    product_variant=pvw.product_variant,
                    warehouse=pvw.warehouse,
                    movement_type=StockMovement.MovementType.ADJUSTMENT,
                    field_change="physical_qty",
                    quantity=new_qty - balance_before,
                    balance_before=balance_before,
                    balance_after=new_qty,
                    reference_number="BULK_ADJ",
                    note=f"Bulk {update_type}: {qty}",
                )

                results.append(
                    {
                        "variant_id": variant_id,
                        "warehouse_id": warehouse_id,
                        "old_qty": balance_before,
                        "new_qty": new_qty,
                    }
                )

            except ProductVariantWarehouse.DoesNotExist:
                errors.append(
                    {
                        "variant_id": variant_id,
                        "warehouse_id": warehouse_id,
                        "error": "Stock record not found. Create a warehouse stock entry first.",
                    }
                )
            except Exception as e:
                errors.append(
                    {"variant_id": variant_id, "warehouse_id": warehouse_id, "error": str(e)}
                )

        return {
            "results": results,
            "errors": errors,
            "summary": {"total": len(updates), "successful": len(results), "failed": len(errors)},
        }
