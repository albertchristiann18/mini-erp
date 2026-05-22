from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.omnichannel.vendor.tiktok.models import TikTokShop, TikTokSyncLog
from apps.omnichannel.vendor.tiktok.stock_sync import TikTokStockSyncer


class Command(BaseCommand):
    help = "Push stock levels to TikTok for all active shops"

    def handle(self, *args, **options):
        for shop in TikTokShop.objects.filter(is_active=True):
            log = TikTokSyncLog.objects.create(shop=shop, sync_type="stock", status="running")
            try:
                syncer = TikTokStockSyncer(shop)
                count = syncer.push_stock()
                log.status = "success"
                log.orders_synced = count
                self.stdout.write(
                    self.style.SUCCESS(f"Shop {shop.shop_id}: pushed {count} stock records")
                )
            except Exception as e:
                log.status = "error"
                log.message = str(e)
            finally:
                log.finished_at = timezone.now()
                log.save()
