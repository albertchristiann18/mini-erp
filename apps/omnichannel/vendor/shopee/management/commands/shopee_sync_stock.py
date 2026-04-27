from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.omnichannel.vendor.shopee.models import ShopeeShop, ShopeeSyncLog
from apps.omnichannel.vendor.shopee.stock_sync import ShopeeStockSyncer


class Command(BaseCommand):
    help = "Sync stock from Shopee for all active shops"

    def handle(self, *args, **options):
        for shop in ShopeeShop.objects.filter(is_active=True):
            log = ShopeeSyncLog.objects.create(shop=shop, sync_type="stock", status="running")
            try:
                syncer = ShopeeStockSyncer(shop)
                count = syncer.pull_stock_from_shopee()
                log.status = "success"
                log.records_synced = count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Shop {shop.shop_id}: synced {count} stock records"
                    )
                )
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
            finally:
                log.finished_at = timezone.now()
                log.save()
