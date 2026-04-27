import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.shopee.client import ShopeeAPIError
from apps.shopee.models import ShopeeShop, ShopeeSyncLog
from apps.shopee.order_sync import ShopeeOrderSyncer

logger = logging.getLogger(__name__)


def sync_orders_for_shop(shop: ShopeeShop, hours_back: int = 24) -> int:
    """Sync recent orders for a shop. Returns count of orders synced."""
    syncer = ShopeeOrderSyncer(shop)
    client = syncer.client

    time_to = int(timezone.now().timestamp())
    time_from = int((timezone.now() - timedelta(hours=hours_back)).timestamp())

    count = 0
    cursor = ""

    while True:
        try:
            response = client.get_order_list(
                time_range_field="create_time",
                time_from=time_from,
                time_to=time_to,
                page_size=50,
                cursor=cursor,
            )
        except ShopeeAPIError as e:
            logger.error(f"Failed to get order list for shop {shop.shop_id}: {e}")
            break

        order_list = response.get("order_list", [])
        order_sns = [o["order_sn"] for o in order_list if "order_sn" in o]

        if order_sns:
            for i in range(0, len(order_sns), 50):
                batch = order_sns[i : i + 50]
                try:
                    detail_response = client.get_order_detail(batch)
                    for order_data in detail_response.get("order_list", []):
                        syncer._upsert_order(order_data)
                        count += 1
                except ShopeeAPIError as e:
                    logger.error(f"Failed to get order details: {e}")

        if not response.get("more", False):
            break
        cursor = response.get("next_cursor", "")
        if not cursor:
            break

    shop.last_order_sync_at = timezone.now()
    shop.save(update_fields=["last_order_sync_at"])
    return count


class Command(BaseCommand):
    help = "Sync orders from Shopee for all active shops"

    def add_arguments(self, parser):
        parser.add_argument("--shop-id", type=int, help="Sync only this shop_id")
        parser.add_argument("--hours", type=int, default=24, help="Hours back to sync")

    def handle(self, *args, **options):
        shops = ShopeeShop.objects.filter(is_active=True)
        if options.get("shop_id"):
            shops = shops.filter(shop_id=options["shop_id"])

        for shop in shops:
            log = ShopeeSyncLog.objects.create(shop=shop, sync_type="orders", status="running")
            try:
                count = sync_orders_for_shop(shop, hours_back=options["hours"])
                log.status = "success"
                log.records_synced = count
                self.stdout.write(
                    self.style.SUCCESS(f"Shop {shop.shop_id}: synced {count} orders")
                )
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                self.stdout.write(self.style.ERROR(f"Shop {shop.shop_id}: {e}"))
            finally:
                log.finished_at = timezone.now()
                log.save()
