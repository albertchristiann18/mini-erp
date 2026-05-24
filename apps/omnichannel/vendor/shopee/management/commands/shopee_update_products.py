import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.omnichannel.vendor.shopee.models import ShopeeShop, ShopeeSyncLog
from apps.omnichannel.vendor.shopee.product_push import ShopeeProductPushService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-sync all already-linked products from ERP to Shopee"

    def handle(self, *args: object, **options: object) -> None:
        from apps.inventory.models import Product, ProductVariantMarketplace

        shops = ShopeeShop.objects.filter(is_active=True).select_related("marketplace")
        service = ShopeeProductPushService()

        for shop in shops:
            if not shop.marketplace:
                continue

            linked_product_ids = (
                ProductVariantMarketplace.objects.filter(
                    marketplace=shop.marketplace,
                    is_active=True,
                    shopee_item_id__isnull=False,
                )
                .values_list("product_variant__product_id", flat=True)
                .distinct()
            )
            products = Product.objects.filter(id__in=linked_product_ids).select_related("category")

            log = ShopeeSyncLog.objects.create(
                shop=shop, sync_type="product_update", status="running"
            )
            updated_count = 0
            all_errors: list[str] = []

            for product in products:
                result = service.update_product(product, shop)
                if result["updated"]:
                    updated_count += 1
                if result["errors"]:
                    all_errors.extend([f"{product.sku_code}: {e}" for e in result["errors"]])

            log.status = "success"
            log.records_synced = updated_count
            log.error_message = "\n".join(all_errors[:50])
            log.finished_at = timezone.now()
            log.save(update_fields=["status", "records_synced", "error_message", "finished_at"])
            self.stdout.write(
                f"Shop {shop.shop_id}: updated={updated_count} errors={len(all_errors)}"
            )
