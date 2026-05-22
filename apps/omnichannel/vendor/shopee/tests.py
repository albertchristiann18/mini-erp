import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import requests
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
from apps.omnichannel.vendor.shopee.client import ShopeeClient
from apps.omnichannel.vendor.shopee.exceptions import ShopeeAPIError, ShopeeAuthError
from apps.omnichannel.vendor.shopee.factories import ShopeeShopFactory, ShopeeWebhookLogFactory
from apps.omnichannel.vendor.shopee.models import ShopeeWebhookLog
from apps.omnichannel.vendor.shopee.utils import sign_shop_api
from apps.sales.models import SalesOrder
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


class TestShopeeClientSign(TestCase):
    """_sign() produces correct HMAC-SHA256 output."""

    def setUp(self):
        self.shop = ShopeeShopFactory(
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client = ShopeeClient(self.shop)

    @patch("time.time", return_value=1700000000)
    def test_sign_produces_correct_hmac(self, mock_time: MagicMock) -> None:
        sign, timestamp = self.client._sign("/api/v2/test")
        self.assertEqual(timestamp, 1700000000)
        expected_base = (
            f"{self.shop.partner_id}/api/v2/test1700000000"
            f"{self.shop.access_token}{self.shop.shop_id}"
        )
        expected = hmac.new(
            self.shop.partner_key.encode(),
            expected_base.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(sign, expected)

    @patch("time.time", return_value=1700000000)
    def test_sign_base_string_format(self, mock_time: MagicMock) -> None:
        sign, _ = self.client._sign("/api/v2/order/get_order_list")
        expected_base = (
            f"{self.shop.partner_id}/api/v2/order/get_order_list1700000000"
            f"{self.shop.access_token}{self.shop.shop_id}"
        )
        expected = hmac.new(
            self.shop.partner_key.encode(),
            expected_base.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(sign, expected)


class TestShopeeClientBuildUrl(TestCase):
    """_build_url() includes all required Shopee common params."""

    def setUp(self):
        self.shop = ShopeeShopFactory(
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client = ShopeeClient(self.shop)

    @patch("time.time", return_value=1700000000)
    def test_build_url_contains_all_common_params(self, mock_time: MagicMock) -> None:
        url = self.client._build_url("/api/v2/test_path")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertEqual(parsed.path, "/api/v2/test_path")
        self.assertEqual(int(qs["partner_id"][0]), self.shop.partner_id)
        self.assertEqual(int(qs["shop_id"][0]), self.shop.shop_id)
        self.assertEqual(int(qs["timestamp"][0]), 1700000000)
        self.assertEqual(qs["access_token"][0], self.shop.access_token)
        self.assertIn("sign", qs)
        self.assertEqual(len(qs["sign"][0]), 64)

    @patch("time.time", return_value=1700000000)
    def test_build_url_merges_extra_params(self, mock_time: MagicMock) -> None:
        url = self.client._build_url(
            "/api/v2/test_path",
            extra_params={"item_id_list": "123,456", "need_tax_info": "false"},
        )
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertEqual(qs["item_id_list"][0], "123,456")
        self.assertEqual(qs["need_tax_info"][0], "false")
        self.assertIn("partner_id", qs)
        self.assertIn("sign", qs)


class TestShopeeClientGet(TestCase):
    """get() raises ShopeeAPIError on failure responses."""

    def setUp(self):
        self.shop = ShopeeShopFactory(
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client = ShopeeClient(self.shop)

    @patch("requests.get")
    def test_get_raises_on_http_error(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_get.return_value = mock_resp

        with self.assertRaises(ShopeeAPIError) as ctx:
            self.client.get("/api/v2/test")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "HTTP_ERROR")
        self.assertEqual(ctx.exception.message, "Bad Request")

    @patch("requests.get")
    def test_get_raises_on_shopee_error_body(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": "some_error",
            "message": "Something went wrong",
        }
        mock_get.return_value = mock_resp

        with self.assertRaises(ShopeeAPIError) as ctx:
            self.client.get("/api/v2/test")
        self.assertEqual(ctx.exception.error_code, "some_error")
        self.assertEqual(ctx.exception.message, "Something went wrong")

    @patch("requests.get")
    def test_get_returns_response_field(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": {"data": "value"}}
        mock_get.return_value = mock_resp

        result = self.client.get("/api/v2/test")
        self.assertEqual(result, {"data": "value"})


class TestShopeeClientRefreshToken(TestCase):
    """refresh_access_token() saves new token and returns True/False."""

    def setUp(self):
        self.shop = ShopeeShopFactory(
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client = ShopeeClient(self.shop)

    @patch("requests.post")
    def test_refresh_success_saves_token(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expire_in": 14400,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.client.refresh_access_token()

        self.assertTrue(result)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.access_token, "new_access_token")
        self.assertEqual(self.shop.refresh_token, "new_refresh_token")
        self.assertIsNotNone(self.shop.token_expires_at)

    @patch("requests.post")
    def test_refresh_http_failure_returns_false(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.RequestException("Connection error")
        mock_post.return_value = mock_resp

        result = self.client.refresh_access_token()

        self.assertFalse(result)

    @patch("requests.post")
    def test_refresh_shopee_error_body_returns_false(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "error": "auth_failure",
            "message": "Invalid refresh token",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = self.client.refresh_access_token()

        self.assertFalse(result)


class TestShopeeClientAutoRefresh(TestCase):
    """_ensure_token_fresh() auto-refreshes when token is near expiry."""

    def setUp(self):
        self.shop = ShopeeShopFactory(
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client = ShopeeClient(self.shop)

    @patch.object(ShopeeClient, "refresh_access_token", return_value=True)
    def test_auto_refresh_triggers_when_expiring_soon(self, mock_refresh: MagicMock) -> None:
        self.shop.token_expires_at = timezone.now() + timedelta(minutes=5)
        self.client._ensure_token_fresh()
        mock_refresh.assert_called_once()

    @patch.object(ShopeeClient, "refresh_access_token", return_value=False)
    def test_raises_auth_error_when_refresh_fails(self, mock_refresh: MagicMock) -> None:
        self.shop.token_expires_at = timezone.now() + timedelta(minutes=5)
        with self.assertRaises(ShopeeAuthError):
            self.client._ensure_token_fresh()
        mock_refresh.assert_called_once()

    @patch.object(ShopeeClient, "refresh_access_token")
    def test_no_refresh_when_token_is_fresh(self, mock_refresh: MagicMock) -> None:
        self.shop.token_expires_at = timezone.now() + timedelta(hours=1)
        self.client._ensure_token_fresh()
        mock_refresh.assert_not_called()

    @patch.object(ShopeeClient, "refresh_access_token")
    def test_no_refresh_when_token_expires_at_is_none(self, mock_refresh: MagicMock) -> None:
        self.shop.token_expires_at = None
        self.client._ensure_token_fresh()
        mock_refresh.assert_not_called()
