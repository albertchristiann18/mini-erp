import logging
from datetime import timedelta
from typing import Any, Dict, Optional

import requests
from django.utils import timezone

from apps.omnichannel.vendor.shopee.models import ShopeeShop
from apps.omnichannel.vendor.shopee.utils import get_timestamp, sign_public_api, sign_shop_api

logger = logging.getLogger(__name__)


class ShopeeAPIError(Exception):
    def __init__(self, error_code: str, message: str, request_id: str = ""):
        self.error_code = error_code
        self.message = message
        self.request_id = request_id
        super().__init__(f"[{error_code}] {message} (request_id={request_id})")


class ShopeeClient:
    """Handles all Shopee API v2.0 calls for a single shop."""

    def __init__(self, shop: ShopeeShop):
        self.shop = shop

    def _ensure_token_fresh(self) -> None:
        """Refresh access token if expired or about to expire (within 10 min)."""
        if not self.shop.token_expires_at:
            return
        if timezone.now() >= self.shop.token_expires_at - timedelta(minutes=10):
            self.refresh_access_token()

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        self._ensure_token_fresh()
        ts = get_timestamp()
        sign = sign_shop_api(
            self.shop.partner_id,
            path,
            ts,
            self.shop.access_token,
            self.shop.shop_id,
            self.shop.partner_key,
        )
        url = f"{self.shop.base_url}{path}"
        query = {
            "partner_id": self.shop.partner_id,
            "timestamp": ts,
            "access_token": self.shop.access_token,
            "shop_id": self.shop.shop_id,
            "sign": sign,
            **(params or {}),
        }
        resp = requests.get(url, params=query, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise ShopeeAPIError(data["error"], data.get("message", ""), data.get("request_id", ""))
        return data.get("response", data)

    def _post(self, path: str, body: Dict, params: Optional[Dict] = None) -> Any:
        self._ensure_token_fresh()
        ts = get_timestamp()
        sign = sign_shop_api(
            self.shop.partner_id,
            path,
            ts,
            self.shop.access_token,
            self.shop.shop_id,
            self.shop.partner_key,
        )
        url = f"{self.shop.base_url}{path}"
        query = {
            "partner_id": self.shop.partner_id,
            "timestamp": ts,
            "access_token": self.shop.access_token,
            "shop_id": self.shop.shop_id,
            "sign": sign,
            **(params or {}),
        }
        resp = requests.post(url, params=query, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise ShopeeAPIError(data["error"], data.get("message", ""), data.get("request_id", ""))
        return data.get("response", data)

    def refresh_access_token(self) -> None:
        """Use refresh_token to get a new access_token."""
        path = "/api/v2/auth/access_token/get"
        ts = get_timestamp()
        sign = sign_public_api(self.shop.partner_id, path, ts, self.shop.partner_key)
        url = f"{self.shop.base_url}{path}"
        query = {"partner_id": self.shop.partner_id, "timestamp": ts, "sign": sign}
        body = {
            "partner_id": self.shop.partner_id,
            "shop_id": self.shop.shop_id,
            "refresh_token": self.shop.refresh_token,
        }
        resp = requests.post(url, params=query, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise ShopeeAPIError(data["error"], data.get("message", ""))

        self.shop.access_token = data["access_token"]
        self.shop.refresh_token = data["refresh_token"]
        self.shop.token_expires_at = timezone.now() + timedelta(
            seconds=data.get("expire_in", 14400)
        )
        self.shop.save(update_fields=["access_token", "refresh_token", "token_expires_at"])
        logger.info(f"Refreshed token for shop {self.shop.shop_id}")

    # ── Order APIs ──────────────────────────────────────────────────────────

    def get_order_list(
        self,
        time_range_field: str = "create_time",
        time_from: int = 0,
        time_to: int = 0,
        page_size: int = 50,
        cursor: str = "",
    ) -> Any:
        """GET /api/v2/order/get_order_list"""
        params: Dict[str, Any] = {
            "time_range_field": time_range_field,
            "time_from": time_from,
            "time_to": time_to,
            "page_size": page_size,
            "order_status": "READY_TO_SHIP",
        }
        if cursor:
            params["cursor"] = cursor
        return self._get("/api/v2/order/get_order_list", params)

    def get_order_detail(self, order_sn_list: list) -> Any:
        """GET /api/v2/order/get_order_detail"""
        return self._get(
            "/api/v2/order/get_order_detail",
            {
                "order_sn_list": ",".join(order_sn_list),
                "response_optional_fields": "buyer_user_id,buyer_username,estimated_shipping_fee,recipient_address,actual_shipping_fee,goods_to_declare,note,note_update_time,item_list,pay_time,dropshipper,dropshipper_phone,split_up,buyer_cancel_reason,cancel_by,cancel_reason,actual_shipping_fee_confirmed,buyer_cpf_id,fulfillment_flag,pickup_done_time,package_list,shipping_carrier,payment_method,total_amount,buyer_username,invoice_data,checkout_shipping_carrier,reverse_shipping_fee,order_chargeable_weight_gram",
            },
        )

    def ship_order(
        self, order_sn: str, tracking_number: str = "", pickup_time_id: str = ""
    ) -> Any:
        """POST /api/v2/logistics/ship_order"""
        body: Dict[str, Any] = {"order_sn": order_sn}
        if tracking_number:
            body["package_number"] = ""
            body["dropoff"] = {"tracking_no": tracking_number}
        return self._post("/api/v2/logistics/ship_order", body)

    # ── Product APIs ─────────────────────────────────────────────────────────

    def get_item_list(
        self, offset: int = 0, page_size: int = 50, item_status: str = "NORMAL"
    ) -> Any:
        """GET /api/v2/product/get_item_list"""
        return self._get(
            "/api/v2/product/get_item_list",
            {
                "offset": offset,
                "page_size": page_size,
                "item_status": item_status,
            },
        )

    def get_item_base_info(self, item_id_list: list) -> Any:
        """GET /api/v2/product/get_item_base_info"""
        return self._get(
            "/api/v2/product/get_item_base_info",
            {
                "item_id_list": ",".join(str(i) for i in item_id_list),
                "need_tax_info": False,
                "need_complaint_policy": False,
            },
        )

    def update_stock(self, item_id: int, model_list: list) -> Any:
        """POST /api/v2/product/update_stock — update stock for variants"""
        return self._post(
            "/api/v2/product/update_stock",
            {
                "item_id": item_id,
                "stock_list": model_list,
            },
        )

    # ── Shop APIs ────────────────────────────────────────────────────────────

    def get_shop_info(self) -> Any:
        """GET /api/v2/shop/get_shop_info"""
        return self._get("/api/v2/shop/get_shop_info")

    # ── Finance APIs ─────────────────────────────────────────────────────────

    def get_escrow_detail(self, order_sn: str) -> Any:
        """GET /api/v2/payment/get_escrow_detail — get payout info for an order"""
        return self._get("/api/v2/payment/get_escrow_detail", {"order_sn": order_sn})
