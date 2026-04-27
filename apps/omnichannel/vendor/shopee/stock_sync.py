import logging

from apps.inventory.models import ProductVariant, ProductVariantMarketplace, ProductVariantWarehouse
from apps.omnichannel.vendor.shopee.client import ShopeeClient, ShopeeAPIError
from apps.omnichannel.vendor.shopee.models import ShopeeShop

logger = logging.getLogger(__name__)


class ShopeeStockSyncer:

    def __init__(self, shop: ShopeeShop):
        self.shop = shop
        self.client = ShopeeClient(shop)

    def push_stock_to_shopee(self) -> int:
        """Push our current stock levels to Shopee for all linked variants."""
        if not self.shop.marketplace:
            logger.warning(f"Shop {self.shop.shop_id} has no linked marketplace")
            return 0

        listings = ProductVariantMarketplace.objects.filter(
            marketplace=self.shop.marketplace,
            is_active=True,
        ).select_related("product_variant")

        logger.info(f"Stock sync: found {listings.count()} listings for shop {self.shop.shop_id}")

        count = 0
        # TODO: implement once ShopeeItemMapping model is added
        return count

    def pull_stock_from_shopee(self) -> int:
        """Pull stock levels from Shopee and update our ProductVariantWarehouse."""
        if not self.shop.default_warehouse or not self.shop.marketplace:
            return 0

        count = 0
        offset = 0
        page_size = 50

        while True:
            try:
                response = self.client.get_item_list(offset=offset, page_size=page_size)
            except ShopeeAPIError as e:
                logger.error(f"Failed to get item list: {e}")
                break

            items = response.get("item", [])
            if not items:
                break

            for item in items:
                item_id = item.get("item_id")
                try:
                    detail = self.client.get_item_base_info([item_id])
                    item_list = detail.get("item_list", [])
                    for item_detail in item_list:
                        for model in item_detail.get("model", []):
                            sku = model.get("model_sku", "")
                            stock = (
                                model.get("stock_info_v2", {})
                                .get("seller_stock", [{}])[0]
                                .get("stock", 0)
                            )
                            if sku:
                                variant = ProductVariant.objects.filter(
                                    sku_variant_code=sku
                                ).first()
                                if variant:
                                    pvw, _ = ProductVariantWarehouse.objects.get_or_create(
                                        product_variant=variant,
                                        warehouse=self.shop.default_warehouse,
                                        defaults={
                                            "company": self.shop.company,
                                        },
                                    )
                                    pvw.physical_qty = stock
                                    pvw.save(update_fields=["physical_qty"])
                                    count += 1
                except ShopeeAPIError as e:
                    logger.error(f"Failed to get item detail for {item_id}: {e}")

            if not response.get("has_next_page", False):
                break
            offset += page_size

        return count
