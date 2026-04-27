import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.inventory.factories import (
    ProductCogsFactory,
    ProductFactory,
    ProductVariantFactory,
    ProductVariantWarehouseFactory,
)
from apps.sales.models import SalesOrder
from apps.omnichannel.vendor.shopee.factories import ShopeeShopFactory, ShopeeWebhookLogFactory
from apps.omnichannel.vendor.shopee.models import ShopeeShop, ShopeeWebhookLog
from apps.omnichannel.vendor.shopee.utils import sign_shop_api
from core.factories import CompanyFactory, MarketplaceFactory, WarehouseFactory


class ShopeeWebhookAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = CompanyFactory()
        self.shop = ShopeeShopFactory(company=self.company)

    def test_webhook_receives_order_event(self):
        payload = {
            "code": 3,
            "shop_id": self.shop.shop_id,
            "ordersn": "SH_ORDER_001",
            "status": "READY_TO_SHIP",
        }
        response = self.client.post(
            "/shopee/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShopeeWebhookLog.objects.count(), 1)
        log = ShopeeWebhookLog.objects.first()
        self.assertEqual(log.shop_id, self.shop.shop_id)
        self.assertEqual(log.event_code, 3)

    def test_webhook_invalid_json(self):
        response = self.client.post(
            "/shopee/webhook/",
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class ShopeeOrderSyncTest(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.marketplace = MarketplaceFactory()
        self.product = ProductFactory(company=self.company)
        self.variant = ProductVariantFactory(
            product=self.product,
            company=self.company,
            total_available_qty=100,
        )
        self.variant.refresh_from_db()  # Get trigger-generated sku_variant_code
        self.pvw = ProductVariantWarehouseFactory(
            product_variant=self.variant,
            warehouse=self.warehouse,
            company=self.company,
            physical_qty=100,
        )
        self.cogs = ProductCogsFactory(
            product_variant=self.variant,
            warehouse=self.warehouse,
            company=self.company,
            original_qty=100,
            remaining_qty=100,
            cogs_amount=50000,
        )
        self.shop = ShopeeShopFactory(
            company=self.company,
            marketplace=self.marketplace,
            default_warehouse=self.warehouse,
        )

    @patch("apps.omnichannel.vendor.shopee.order_sync.ShopeeClient")
    def test_order_upsert_creates_sales_order(self, MockClient):
        sku = self.variant.sku_variant_code
        mock_client = MockClient.return_value
        mock_client.get_order_detail.return_value = {
            "order_list": [
                {
                    "order_sn": "SH_ORDER_001",
                    "order_status": "READY_TO_SHIP",
                    "create_time": int(timezone.now().timestamp()),
                    "total_amount": 200000,
                    "actual_shipping_fee": 10000,
                    "shipping_carrier": "JNE",
                    "tracking_number": "TRK001",
                    "recipient_address": {
                        "name": "John Doe",
                        "phone": "08123456789",
                        "full_address": "Jl. Test 123",
                        "city": "Jakarta",
                        "state": "DKI Jakarta",
                    },
                    "item_list": [
                        {
                            "item_id": 12345,
                            "item_sku": sku,
                            "model_sku": sku,
                            "model_original_price": 100000,
                            "model_quantity_purchased": 2,
                        }
                    ],
                }
            ]
        }

        from apps.omnichannel.vendor.shopee.order_sync import ShopeeOrderSyncer

        syncer = ShopeeOrderSyncer(self.shop)
        so = syncer.sync_order_by_sn("SH_ORDER_001")

        self.assertIsNotNone(so)
        self.assertEqual(so.marketplace_order_id, "SH_ORDER_001")
        self.assertEqual(so.customer_name, "John Doe")
        self.assertEqual(so.items.count(), 1)
        item = so.items.first()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.selling_price, 100000)

    @patch("apps.omnichannel.vendor.shopee.order_sync.ShopeeClient")
    def test_order_upsert_skips_duplicate(self, MockClient):
        sku = self.variant.sku_variant_code
        mock_client = MockClient.return_value
        mock_client.get_order_detail.return_value = {
            "order_list": [
                {
                    "order_sn": "SH_ORDER_DUP",
                    "order_status": "READY_TO_SHIP",
                    "create_time": int(timezone.now().timestamp()),
                    "total_amount": 100000,
                    "actual_shipping_fee": 0,
                    "shipping_carrier": "",
                    "tracking_number": "",
                    "recipient_address": {
                        "name": "Jane",
                        "phone": "081",
                        "full_address": "Addr",
                        "city": "City",
                        "state": "State",
                    },
                    "item_list": [
                        {
                            "item_id": 1,
                            "model_sku": sku,
                            "model_original_price": 100000,
                            "model_quantity_purchased": 1,
                        }
                    ],
                }
            ]
        }

        from apps.omnichannel.vendor.shopee.order_sync import ShopeeOrderSyncer

        syncer = ShopeeOrderSyncer(self.shop)
        so1 = syncer.sync_order_by_sn("SH_ORDER_DUP")
        so2 = syncer.sync_order_by_sn("SH_ORDER_DUP")

        self.assertIsNotNone(so1)
        self.assertIsNotNone(so2)
        self.assertEqual(SalesOrder.objects.filter(marketplace_order_id="SH_ORDER_DUP").count(), 1)


class ShopeeShopAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = CompanyFactory()
        self.shop = ShopeeShopFactory(company=self.company)

    def test_shopee_shop_api_list(self):
        response = self.client.get("/shopee/shops/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_webhook_log_api_list(self):
        ShopeeWebhookLogFactory(shop_id=self.shop.shop_id)
        response = self.client.get("/shopee/webhook-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ShopeeUtilsTest(TestCase):
    def test_sign_shop_api(self):
        sig = sign_shop_api(
            partner_id=12345,
            path="/api/v2/order/get_order_list",
            timestamp=1700000000,
            access_token="tok123",
            shop_id=999,
            partner_key="secret_key",
        )
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)  # SHA256 hex digest length

        # Same inputs should produce same output
        sig2 = sign_shop_api(
            partner_id=12345,
            path="/api/v2/order/get_order_list",
            timestamp=1700000000,
            access_token="tok123",
            shop_id=999,
            partner_key="secret_key",
        )
        self.assertEqual(sig, sig2)

        # Different inputs should produce different output
        sig3 = sign_shop_api(
            partner_id=12345,
            path="/api/v2/order/get_order_list",
            timestamp=1700000001,
            access_token="tok123",
            shop_id=999,
            partner_key="secret_key",
        )
        self.assertNotEqual(sig, sig3)


class ShopeeRefreshTokenTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = CompanyFactory()
        self.shop = ShopeeShopFactory(company=self.company)

    @patch("requests.post")
    def test_refresh_token_action(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expire_in": 14400,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.client.post(f"/shopee/shops/{self.shop.id}/refresh-token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.shop.refresh_from_db()
        self.assertEqual(self.shop.access_token, "new_access_token")
        self.assertEqual(self.shop.refresh_token, "new_refresh_token")
