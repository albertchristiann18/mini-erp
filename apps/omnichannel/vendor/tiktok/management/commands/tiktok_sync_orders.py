import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.omnichannel.vendor.tiktok.models import TikTokShop, TikTokSyncLog
from apps.omnichannel.vendor.tiktok.order_sync import TikTokOrderSyncer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync orders from TikTok for all active shops"

    def add_arguments(self, parser):
        parser.add_argument("--shop-id", type=str, help="Sync only this shop_id")

    def handle(self, *args, **options):
        shops = TikTokShop.objects.filter(is_active=True)
        if options.get("shop_id"):
            shops = shops.filter(shop_id=options["shop_id"])

        for shop in shops:
            log = TikTokSyncLog.objects.create(shop=shop, sync_type="orders", status="running")
            try:
                syncer = TikTokOrderSyncer(shop)
                count = syncer.sync_orders()
                log.status = "success"
                log.orders_synced = count
                self.stdout.write(self.style.SUCCESS(f"Shop {shop.shop_id}: synced {count} orders"))
            except Exception as e:
                log.status = "error"
                log.message = str(e)
                self.stdout.write(self.style.ERROR(f"Shop {shop.shop_id}: {e}"))
            finally:
                log.finished_at = timezone.now()
                log.save()
