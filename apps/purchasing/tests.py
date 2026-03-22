from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.factories import (
    CategoryFactory,
    CompanyFactory,
    ProductCogsFactory,
    ProductFactory,
    ProductVariantFactory,
    ProductVariantWarehouseFactory,
)
from apps.inventory.models import (
    ProductCogs,
    ProductVariantWarehouse,
)
from apps.purchasing.factories import (
    PurchaseOrderDetailFactory,
    PurchaseOrderFactory,
)
from apps.purchasing.models import PurchaseOrder
from apps.purchasing.serializers import PurchaseOrderUpdateSerializer
from apps.purchasing.services.purchasing_service import PurchaseOrderService
from core.factories import WarehouseFactory


class PurchaseOrderAPITest(TestCase):
    """API test cases for Purchase Orders"""

    def setUp(self):
        self.client = APIClient()
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.category = CategoryFactory(company=self.company)
        self.product = ProductFactory(category=self.category, company=self.company)
        self.product_variant = ProductVariantFactory(product=self.product)

    def test_get_single_po_with_details(self):
        """Get 1 PO and the details"""
        po = PurchaseOrderFactory(warehouse=self.warehouse, company=self.company)
        PurchaseOrderDetailFactory(purchase_order=po, product_variant=self.product_variant)

        response = self.client.get(f"/purchase-order/{po.id}/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(po.id))
        self.assertEqual(len(response.data["order_details"]), 1)

    def test_get_list_of_two_pos(self):
        """Get list of 2 POs"""
        po1 = PurchaseOrderFactory(warehouse=self.warehouse, company=self.company)
        PurchaseOrderFactory(warehouse=self.warehouse, company=self.company)

        response = self.client.get("/purchase-order/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["id"], str(po1.id))

    def test_create_po(self):
        """Create a PO"""
        payload = {
            "warehouse_id": str(self.warehouse.id),
            "company_id": str(self.company.id),
            "supplier_name": "Test Supplier",
            "forwarder_name": "Test Forwarder",
            "shop_services": "Test Shop",
            "commission_fee_pct": 10,
            "delivery_fee": 100,
            "currency": "RMB",
            "exchange_rate": 2200,
            "total_ordered_qty": 100,
            "total_amount": 1000000,
            "order_details": [
                {
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 100,
                    "unit_price_foreign": 100,
                }
            ],
        }

        response = self.client.post("/purchase-order/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        purchase_order = PurchaseOrder.objects.last()
        self.assertTrue(purchase_order.purchase_order_number.startswith("PO-2026-"))


class PurchaseOrderServiceTest(TestCase):
    """Unit tests for PurchaseOrderService"""

    def setUp(self):
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.category = CategoryFactory(company=self.company)
        self.product = ProductFactory(category=self.category, company=self.company)
        self.product_variant = ProductVariantFactory(product=self.product)
        self.service = PurchaseOrderService()

    def test_create_purchase_order_success(self):
        """Test successful creation of purchase order"""
        data = {
            "warehouse_id": str(self.warehouse.id),
            "company_id": str(self.company.id),
            "supplier_name": "Test Supplier",
            "total_ordered_qty": 100,
            "total_amount": 1000000,
            "order_details": [
                {
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 100,
                    "unit_price_foreign": 100,
                }
            ],
        }

        self.service.create_purchase_order(data)

        po = PurchaseOrder.objects.last()
        self.assertIsNotNone(po.purchase_order_number)
        self.assertEqual(po.status, PurchaseOrder.POStatus.DRAFT)
        self.assertEqual(po.order_details.count(), 1)

    def test_update_po_updates_details_when_provided(self):
        """Test that order details are updated when provided"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )

        data = {
            "order_details": [
                {
                    "id": str(detail.id),
                    "ordered_qty": 100,
                }
            ]
        }

        self.service.update_purchase_order(po, data)

        detail.refresh_from_db()
        self.assertEqual(detail.ordered_qty, 100)

    def test_update_po_nonexistent_detail_allowed_in_draft(self):
        """Test that non-existent detail is ignored in DRAFT status (no error raised)"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )

        data = {
            "order_details": [
                {
                    "id": str(uuid4()),
                    "ordered_qty": 100,
                }
            ]
        }

        self.service.update_purchase_order(po, data)

        po.refresh_from_db()
        self.assertEqual(po.order_details.count(), 0)

    def test_update_po_draft_add_new_detail(self):
        """Test adding a new detail to PO in DRAFT status"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )
        detail1 = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )
        product2 = ProductFactory(category=self.category, company=self.company)
        product_variant2 = ProductVariantFactory(product=product2)

        data = {
            "order_details": [
                {
                    "id": str(detail1.id),
                    "ordered_qty": 50,
                },
                {
                    "product_variant_id": str(product_variant2.id),
                    "ordered_qty": 100,
                    "unit_price_foreign": 100,
                },
            ]
        }

        self.service.update_purchase_order(po, data)

        po.refresh_from_db()
        self.assertEqual(po.order_details.count(), 2)

    def test_update_po_draft_remove_and_replace_details(self):
        """Test removing some details and adding new ones in DRAFT status"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )
        detail1 = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )
        detail2 = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=75
        )
        product_variant3 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=200,
            unit_price_foreign=100,
        )

        data = {
            "order_details": [
                {
                    "id": str(detail2.id),
                    "ordered_qty": 100,
                },
                {
                    "id": str(product_variant3.id),
                    "ordered_qty": 200,
                },
            ]
        }

        self.service.update_purchase_order(po, data)

        po.refresh_from_db()
        self.assertEqual(po.order_details.count(), 2)
        self.assertFalse(po.order_details.filter(id=detail1.id).exists())
        self.assertTrue(po.order_details.filter(id=detail2.id).exists())

    def test_update_po_non_draft_update_existing_detail_succeeds(self):
        """Test that updating existing detail in non-DRAFT status succeeds"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )

        data = {
            "order_details": [
                {
                    "id": str(detail.id),
                    "ordered_qty": 100,
                }
            ]
        }

        self.service.update_purchase_order(po, data)

        detail.refresh_from_db()
        self.assertEqual(detail.ordered_qty, 100)

    def test_update_po_delivered_to_completed_success(self):
        """Test that transitioning DELIVERED to COMPLETED succeeds"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
            delivery_date=date.today(),
        )

        data = {"status": PurchaseOrder.POStatus.COMPLETED}

        updated_po = self.service.update_purchase_order(po, data)

        self.assertEqual(updated_po.status, PurchaseOrder.POStatus.COMPLETED)

    def test_order_details_totals_match_purchase_order_totals(self):
        """Test that order_details totals match purchase_order totals."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            commission_fee_pct=0,
            delivery_fee=0,
            cbm=0,
            shipping_fee_per_cbm=0,
            exchange_rate=2200,
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
            discounted_unit_price_foreign=Decimal("10"),
            unit_price_base=22000,
            discounted_unit_price_base=22000,
            total_price_foreign=Decimal("1000"),
            discounted_total_price_foreign=Decimal("1000"),
            total_price_base=220000,
            discounted_total_price_base=220000,
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=50,
            unit_price_foreign=Decimal("20"),
            discounted_unit_price_foreign=Decimal("20"),
            unit_price_base=44000,
            discounted_unit_price_base=44000,
            total_price_foreign=Decimal("1000"),
            discounted_total_price_foreign=Decimal("1000"),
            total_price_base=220000,
            discounted_total_price_base=220000,
        )

        po = self.service.update_purchase_order(po, {})

        po.refresh_from_db()
        self.assertEqual(po.total_ordered_qty, 150)
        self.assertEqual(po.total_received_qty, 0)
        self.assertEqual(po.total_item_amount, 440000)
        self.assertEqual(po.total_order_amount, 440000)
        self.assertEqual(po.total_amount, 440000)


class PurchaseOrderSerializerValidationTest(TestCase):
    """Test cases for PurchaseOrderUpdateSerializer validation"""

    def setUp(self):
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.category = CategoryFactory(company=self.company)
        self.product = ProductFactory(category=self.category, company=self.company)
        self.product_variant = ProductVariantFactory(product=self.product)
        self.service = PurchaseOrderService()

    def _create_serializer(self, po, data, partial=False):
        return PurchaseOrderUpdateSerializer(po, data=data, partial=partial)

    def test_draft_to_ordered_requires_exchange_rate(self):
        """Test that transitioning DRAFT to ORDERED requires exchange_rate"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("exchange_rate", serializer.errors)

    def test_draft_to_ordered_requires_invoice_file(self):
        """Test that transitioning DRAFT to ORDERED requires invoice file"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("purchase_order_invoice_file", serializer.errors)

    def test_draft_to_ordered_requires_invoice_number(self):
        """Test that transitioning DRAFT to ORDERED requires invoice_number"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("invoice_number", serializer.errors)

    def test_draft_to_ordered_requires_invoice_date(self):
        """Test that transitioning DRAFT to ORDERED requires invoice_date"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("invoice_date", serializer.errors)

    def test_draft_to_ordered_requires_order_details(self):
        """Test that transitioning DRAFT to ORDERED requires order_details when none exist"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="Test Forwarder",
            supplier_name="Test Supplier",
            shop_services="Test Shop Service",
            delivery_fee=Decimal("0"),
        )

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.ORDERED,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)

    def test_draft_to_ordered_requires_commission_fee_pct(self):
        """Test that transitioning DRAFT to ORDERED requires commission_fee_pct"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            forwarder_name="Test Forwarder",
            supplier_name="Test Supplier",
            shop_services="Test Shop Services",
            commission_fee_pct=None,
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("commission_fee_pct", serializer.errors)

    def test_draft_to_ordered_requires_forwarder_name(self):
        """Test that transitioning DRAFT to ORDERED requires forwarder_name"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="",
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("forwarder_name", serializer.errors)

    def test_draft_to_ordered_requires_supplier_name(self):
        """Test that transitioning DRAFT to ORDERED requires supplier_name"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="Test Forwarder",
            shop_services="Test Shop Services",
            supplier_name="",
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("supplier_name", serializer.errors)

    def test_draft_to_ordered_requires_shop_services(self):
        """Test that transitioning DRAFT to ORDERED requires shop_services"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="Test Forwarder",
            supplier_name="Test Supplier",
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("shop_services", serializer.errors)

    def test_draft_to_ordered_requires_delivery_fee(self):
        """Test that transitioning DRAFT to ORDERED requires delivery_fee (can be 0)"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="Test Forwarder",
            supplier_name="Test Supplier",
            shop_services="Test Shop Service",
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.ORDERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("delivery_fee", serializer.errors)

    def test_draft_to_ordered_allows_zero_delivery_fee(self):
        """Test that transitioning DRAFT to ORDERED allows delivery_fee=0"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="test.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            commission_fee_pct=Decimal("10"),
            forwarder_name="Test Forwarder",
            supplier_name="Test Supplier",
            shop_services="Test Shop Service",
            delivery_fee=Decimal("0"),
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.ORDERED,
                "order_details": [
                    {
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 100,
                    }
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_ordered_to_shipped_requires_delivery_order_number(self):
        """Test that transitioning ORDERED to SHIPPED requires delivery order number"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.SHIPPED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("delivery_order_number", serializer.errors)

    def test_ordered_to_shipped_requires_delivery_order_file(self):
        """Test that transitioning ORDERED to SHIPPED requires delivery order file"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            delivery_order_number="DO-001",
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.SHIPPED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("delivery_order_file", serializer.errors)

    def test_ordered_to_shipped_requires_shipping_fee(self):
        """Test that transitioning ORDERED to SHIPPED requires shipping_fee"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            delivery_order_number="DO-001",
            delivery_order_file="existing_file.pdf",
            cbm=Decimal("1.5"),
            weight=Decimal("10.0"),
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.SHIPPED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("shipping_fee_per_cbm", serializer.errors)

    def test_ordered_to_shipped_requires_cbm(self):
        """Test that transitioning ORDERED to SHIPPED requires cbm"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            delivery_order_number="DO-001",
            delivery_order_file="existing_file.pdf",
            shipping_fee_per_cbm=1000,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.SHIPPED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("cbm", serializer.errors)

    def test_ordered_to_shipped_requires_weight(self):
        """Test that transitioning ORDERED to SHIPPED requires weight"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            delivery_order_number="DO-001",
            delivery_order_file="existing_file.pdf",
            shipping_fee_per_cbm=1000,
            cbm=Decimal("1.5"),
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.SHIPPED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("weight", serializer.errors)

    def test_shipped_to_delivered_requires_delivery_order_invoice(self):
        """Test that transitioning SHIPPED to DELIVERED requires DO invoice"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            delivery_order_number="DO-001",
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.DELIVERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("delivery_order_invoice_file", serializer.errors)

    def test_invalid_status_transition_raises_error(self):
        """Test that invalid status transition raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )

        serializer = self._create_serializer(po, {"status": PurchaseOrder.POStatus.DELIVERED})

        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_exchange_rate_cannot_change_after_ordered(self):
        """Test that exchange_rate cannot be changed after ORDERED status"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            exchange_rate=2200,
        )

        serializer = self._create_serializer(po, {"exchange_rate": 2300}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("exchange_rate", serializer.errors)

    def test_unit_price_foreign_cannot_change_after_ordered(self):
        """Test that unit_price_foreign cannot be changed after ORDERED status"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        po.refresh_from_db()
        with self.assertRaises(Exception) as context:
            self.service.update_purchase_order(
                po,
                {
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "ordered_qty": 100,
                            "unit_price_foreign": Decimal("15"),
                        }
                    ]
                },
            )

        self.assertIn("order_details", str(context.exception))
        self.assertIn("unit_price_foreign", str(context.exception))

    def test_discounted_unit_price_foreign_cannot_change_after_ordered(self):
        """Test that discounted_unit_price_foreign cannot be changed after ORDERED status"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
            discounted_unit_price_foreign=Decimal("8"),
        )

        po.refresh_from_db()
        with self.assertRaises(Exception) as context:
            self.service.update_purchase_order(
                po,
                {
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "ordered_qty": 100,
                            "unit_price_foreign": Decimal("10"),
                            "discounted_unit_price_foreign": Decimal("6"),
                        }
                    ]
                },
            )

        self.assertIn("order_details", str(context.exception))
        self.assertIn("discounted_unit_price_foreign", str(context.exception))


@pytest.mark.django_db(transaction=True)
class PurchaseOrderCOGSTest(TestCase):
    """Test cases for COGS creation and updates during PO lifecycle"""

    def setUp(self):
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.category = CategoryFactory(company=self.company)
        self.product = ProductFactory(category=self.category, company=self.company)
        self.product_variant = ProductVariantFactory(product=self.product)
        self.service = PurchaseOrderService()

    def test_cogs_created_on_full_delivery(self):
        """Test COGS is created with correct amounts when full received_qty is delivered."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        initial_cogs_count = ProductCogs.objects.count()

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 100,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        )
        self.assertEqual(cogs.count(), initial_cogs_count + 1)

        cogs_record = cogs.first()
        self.assertIsNotNone(cogs_record)
        self.assertEqual(cogs_record.price_rmb, Decimal("10.0000"))
        self.assertEqual(cogs_record.exchange_rate, 2200)
        self.assertEqual(cogs_record.cogs_amount, 22000)
        self.assertEqual(cogs_record.original_qty, 100)
        self.assertEqual(cogs_record.remaining_qty, 100)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 100)
        self.assertEqual(detail.ordered_qty, 100)
        self.assertEqual(detail.received_qty, detail.ordered_qty)

    def test_cogs_created_with_discount(self):
        """Test COGS uses discounted_unit_price_foreign when provided."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
            discounted_unit_price_foreign=Decimal("8"),
        )

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 100,
                            "unit_price_foreign": Decimal("10"),
                            "discounted_unit_price_foreign": Decimal("8"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.price_rmb, Decimal("8.0000"))
        self.assertEqual(cogs.cogs_amount, 17600)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 100)
        self.assertEqual(detail.ordered_qty, 100)
        self.assertEqual(detail.received_qty, detail.ordered_qty)

    def test_cogs_created_on_partial_delivery(self):
        """Test COGS is created with partial received_qty."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 50,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.original_qty, 50)
        self.assertEqual(cogs.remaining_qty, 50)
        self.assertEqual(cogs.cogs_amount, 22000)

    def test_cogs_updated_when_received_qty_increases(self):
        """Test COGS is updated when received_qty is increased on subsequent delivery."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=50,
            updated_qty=50,
            unit_price_foreign=Decimal("10"),
        )

        po.refresh_from_db()

        ProductCogsFactory(
            company=self.company,
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
            price_rmb=Decimal("10.0000"),
            exchange_rate=2200,
            cogs_amount=22000,
            original_qty=50,
            remaining_qty=50,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 80,
                            "updated_qty": 50,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.original_qty, 80)
        self.assertEqual(cogs.remaining_qty, 80)
        self.assertEqual(cogs.cogs_amount, 22000)

    def test_cogs_updated_when_received_qty_decreases(self):
        """Test COGS is updated when received_qty decreases (e.g., user corrected wrong input)."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=50,
            updated_qty=50,
            unit_price_foreign=Decimal("10"),
        )

        po.refresh_from_db()

        ProductCogsFactory(
            company=self.company,
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
            price_rmb=Decimal("10.0000"),
            exchange_rate=2200,
            cogs_amount=22000,
            original_qty=50,
            remaining_qty=50,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 30,
                            "updated_qty": 50,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.original_qty, 30)
        self.assertEqual(cogs.remaining_qty, 30)
        self.assertEqual(cogs.cogs_amount, 22000)

    def test_no_cogs_created_when_received_qty_zero(self):
        """Test no COGS is created when received_qty is 0."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        initial_cogs_count = ProductCogs.objects.count()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 0,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs_count = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
        ).count()

        self.assertEqual(
            cogs_count, initial_cogs_count, "No COGS should be created when received_qty is 0"
        )

    def test_cogs_with_allocated_shipping_and_delivery_fees_single_item(self):
        """Test COGS includes allocated shipping and delivery fees per unit for single item."""
        product = self.product_variant.product
        product.length = 10
        product.width = 10
        product.height = 10
        product.save()

        shipping_fee_per_cbm = 100000
        cbm = Decimal("0.01")
        shipping_fee = int(shipping_fee_per_cbm * cbm)  # 1000

        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
            shipping_fee_per_cbm=shipping_fee_per_cbm,
            cbm=cbm,
            shipping_fee=shipping_fee,
            delivery_fee=Decimal("100.5"),  # 100.5 RMB
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
            unit_price_foreign=Decimal("10"),
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 10,
                            "received_qty": 10,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        }
                    ],
                },
            )

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.original_qty, 10)
        self.assertEqual(cogs.remaining_qty, 10)

        unit_price_idr = 10 * 2200  # 22000
        allocated_shipping = 1000  # shipping_fee (IDR) = 1000
        allocated_delivery = int(100.5 * 2200)  # 221100
        total_allocated = allocated_shipping + allocated_delivery  # 222100
        shipping_per_unit = total_allocated / 10  # 22210
        expected_cogs = unit_price_idr + shipping_per_unit  # 22000 + 22210 = 44210

        self.assertEqual(cogs.cogs_amount, expected_cogs)
        self.assertEqual(cogs.allocated_shipping_fee, allocated_shipping)
        self.assertEqual(cogs.allocated_delivery_fee, allocated_delivery)

    def test_cogs_with_allocated_fees_multiple_items_same_volume(self):
        """Test COGS with multiple items sharing shipping fees equally when same LxWxH."""
        product1 = self.product_variant.product
        product1.length = 10
        product1.width = 10
        product1.height = 10
        product1.save()

        product2 = ProductFactory(
            category=self.category, company=self.company, length=10, width=10, height=10
        )
        product_variant2 = ProductVariantFactory(product=product2)
        ProductVariantWarehouseFactory(
            product_variant=product_variant2, warehouse=self.warehouse, company=self.company
        )

        shipping_fee_per_cbm = 100000
        cbm = Decimal("0.01")
        shipping_fee = int(shipping_fee_per_cbm * cbm)  # 1000

        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
            shipping_fee_per_cbm=shipping_fee_per_cbm,
            cbm=cbm,
            shipping_fee=shipping_fee,
            delivery_fee=Decimal("0"),
        )

        detail1 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
            unit_price_foreign=Decimal("10"),
        )
        detail2 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=product_variant2,
            ordered_qty=10,
            unit_price_foreign=Decimal("20"),
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail1.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 10,
                            "received_qty": 10,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        },
                        {
                            "id": str(detail2.id),
                            "product_variant_id": str(product_variant2.id),
                            "ordered_qty": 10,
                            "received_qty": 10,
                            "unit_price_foreign": Decimal("20"),
                            "received_date": str(date.today()),
                        },
                    ],
                },
            )

        cogs1 = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()
        cogs2 = ProductCogs.objects.filter(
            product_variant=product_variant2,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs1)
        self.assertIsNotNone(cogs2)

        shipping_fee = 1000  # IDR, already converted
        volume1 = (
            Decimal("10") * Decimal("10") * Decimal("10") / Decimal("1000000") * Decimal("10")
        )  # 0.00001
        volume2 = (
            Decimal("10") * Decimal("10") * Decimal("10") / Decimal("1000000") * Decimal("10")
        )  # 0.00001
        total_volume = volume1 + volume2  # 0.00002

        allocated_shipping1 = int(shipping_fee * volume1 / total_volume)  # 500
        allocated_shipping2 = int(shipping_fee * volume2 / total_volume)  # 500

        expected_cogs1 = 10 * 2200 + allocated_shipping1 / 10  # 22000 + 50 = 22050
        expected_cogs2 = 20 * 2200 + allocated_shipping2 / 10  # 44000 + 50 = 44050

        self.assertEqual(cogs1.cogs_amount, expected_cogs1)
        self.assertEqual(cogs2.cogs_amount, expected_cogs2)
        self.assertEqual(cogs1.allocated_shipping_fee, allocated_shipping1)
        self.assertEqual(cogs2.allocated_shipping_fee, allocated_shipping2)

    def test_cogs_with_allocated_fees_multiple_items_different_volume(self):
        """Test COGS with multiple items where each takes portion of shipping based on volume."""
        product1 = self.product_variant.product
        product1.length = 10
        product1.width = 10
        product1.height = 10  # 0.000001 m3 per item, 0.00001 m3 total for qty=10
        product1.save()

        product2 = ProductFactory(
            category=self.category, company=self.company, length=20, width=20, height=20
        )  # 0.008 m3 per item, 0.08 m3 total for qty=10
        product_variant2 = ProductVariantFactory(product=product2)
        ProductVariantWarehouseFactory(
            product_variant=product_variant2, warehouse=self.warehouse, company=self.company
        )

        shipping_fee_per_cbm = 100000
        cbm = Decimal("0.09")
        shipping_fee = int(shipping_fee_per_cbm * cbm)  # 9000

        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
            shipping_fee_per_cbm=shipping_fee_per_cbm,
            cbm=cbm,
            shipping_fee=shipping_fee,
            delivery_fee=Decimal("0"),
        )

        detail1 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
            unit_price_foreign=Decimal("10"),
        )
        detail2 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=product_variant2,
            ordered_qty=10,
            unit_price_foreign=Decimal("20"),
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail1.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 10,
                            "received_qty": 10,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today()),
                        },
                        {
                            "id": str(detail2.id),
                            "product_variant_id": str(product_variant2.id),
                            "ordered_qty": 10,
                            "received_qty": 10,
                            "unit_price_foreign": Decimal("20"),
                            "received_date": str(date.today()),
                        },
                    ],
                },
            )

        cogs1 = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()
        cogs2 = ProductCogs.objects.filter(
            product_variant=product_variant2,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
        ).first()

        self.assertIsNotNone(cogs1)
        self.assertIsNotNone(cogs2)

        shipping_fee = 9000  # IDR, already converted
        volume1 = (
            Decimal("10") * Decimal("10") * Decimal("10") / Decimal("1000000") * Decimal("10")
        )  # 0.00001
        volume2 = (
            Decimal("20") * Decimal("20") * Decimal("20") / Decimal("1000000") * Decimal("10")
        )  # 0.08
        total_volume = volume1 + volume2  # 0.08001

        allocated_shipping1 = int(shipping_fee * volume1 / total_volume)  # 1
        allocated_shipping2 = int(shipping_fee * volume2 / total_volume)  # 8999

        expected_cogs1 = 10 * 2200 + allocated_shipping1 / 10  # 22000 + 0 = 22000
        expected_cogs2 = 20 * 2200 + allocated_shipping2 / 10  # 44000 + 899 = 44899

        self.assertEqual(cogs1.cogs_amount, expected_cogs1)
        self.assertEqual(cogs2.cogs_amount, expected_cogs2)
        self.assertEqual(cogs1.allocated_shipping_fee, allocated_shipping1)
        self.assertEqual(cogs2.allocated_shipping_fee, allocated_shipping2)

    def test_completed_status_does_not_create_cogs(self):
        """Test transitioning to COMPLETED does not create new COGS."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
            delivery_date=date.today(),
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=80,
        )

        initial_cogs_count = ProductCogs.objects.count()

        self.service.update_purchase_order(po, {"status": PurchaseOrder.POStatus.COMPLETED})

        cogs_count = ProductCogs.objects.filter(
            product_variant=self.product_variant, warehouse=self.warehouse
        ).count()
        self.assertEqual(cogs_count, initial_cogs_count, "COGS should not be created on COMPLETED")


@pytest.mark.django_db(transaction=True)
class PurchaseOrderInventoryUpdateTest(TestCase):
    """Test cases for inventory updates during PO lifecycle"""

    def setUp(self):
        self.company = CompanyFactory()
        self.warehouse = WarehouseFactory(company=self.company)
        self.category = CategoryFactory(company=self.company)
        self.product = ProductFactory(category=self.category, company=self.company)
        self.product_variant = ProductVariantFactory(product=self.product)
        self.service = PurchaseOrderService()

    def test_partial_received_qty_updates_inventory_correctly(self):
        """Test inventory is updated correctly for partial received_qty."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file", return_value=None):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.ORDERED,
                },
            )

        po.refresh_from_db()
        pvw = ProductVariantWarehouse.objects.get(
            product_variant=self.product_variant, warehouse=self.warehouse
        )

        self.assertEqual(po.status, PurchaseOrder.POStatus.ORDERED)
        self.assertEqual(pvw.incoming_qty, 100)
        self.assertEqual(pvw.physical_qty, 0)

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 50,
                            "received_date": str(date.today() + timedelta(days=1)),
                        }
                    ],
                },
            )

        pvw.refresh_from_db()
        self.assertEqual(pvw.incoming_qty, 50)
        self.assertEqual(pvw.physical_qty, 50)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 50)
        self.assertEqual(detail.ordered_qty, 100)
        self.assertEqual(detail.updated_qty, 50)

    def test_incoming_qty_adjusted_when_received_qty_decreased(self):
        """Test incoming_qty is adjusted when received_qty is decreased from SHIPPED to DELIVERED."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        pvw = ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            incoming_qty=100,
            physical_qty=0,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 5,
                            "updated_qty": 0,
                            "received_date": str(date.today() + timedelta(days=1)),
                        }
                    ],
                },
            )

        pvw.refresh_from_db()
        self.assertEqual(pvw.incoming_qty, 95)
        self.assertEqual(pvw.physical_qty, 5)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 5)
        self.assertEqual(detail.ordered_qty, 100)
        self.assertEqual(detail.updated_qty, 5)

    def test_incoming_qty_adjusted_when_already_delivered_and_received_qty_decreased(self):
        """Test incoming_qty adjusted when updating DELIVERED to DELIVERED with decreased received_qty."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=10,
            updated_qty=10,
        )

        pvw = ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            incoming_qty=90,
            physical_qty=10,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 5,
                            "updated_qty": 10,
                            "received_date": str(date.today() + timedelta(days=1)),
                        }
                    ],
                },
            )

        pvw.refresh_from_db()
        self.assertEqual(pvw.incoming_qty, 95)
        self.assertEqual(pvw.physical_qty, 5)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 5)
        self.assertEqual(detail.ordered_qty, 100)
        self.assertEqual(detail.updated_qty, 5)

    def test_incoming_qty_adjusted_when_received_qty_exceeds_ordered(self):
        """Test incoming_qty when received_qty exceeds ordered_qty."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
        )

        pvw = ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            incoming_qty=10,
            physical_qty=0,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 10,
                            "received_qty": 15,
                            "updated_qty": 0,
                            "received_date": str(date.today() + timedelta(days=1)),
                            "remarks": "Over-received due to supplier error",
                        }
                    ],
                },
            )

        pvw.refresh_from_db()
        self.assertEqual(pvw.incoming_qty, 0)
        self.assertEqual(pvw.physical_qty, 15)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 15)
        self.assertEqual(detail.ordered_qty, 10)
        self.assertEqual(detail.updated_qty, 15)

    def test_incoming_qty_adjusted_when_shipped_and_received_qty_exceeds_ordered(self):
        """Test incoming_qty when status is SHIPPED and received_qty exceeds ORDEREDordered_qty (first delivery)."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
        )

        pvw = ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            company=self.company,
            incoming_qty=10,
            physical_qty=0,
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 10,
                            "received_qty": 15,
                            "updated_qty": 0,
                            "received_date": str(date.today() + timedelta(days=1)),
                            "remarks": "Over-received due to supplier error",
                        }
                    ],
                },
            )

        pvw.refresh_from_db()
        self.assertEqual(pvw.incoming_qty, 0)
        self.assertEqual(pvw.physical_qty, 15)

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 15)
        self.assertEqual(detail.ordered_qty, 10)
        self.assertEqual(detail.updated_qty, 15)

    def test_decrease_received_qty_fails_when_insufficient_physical_qty(self):
        """Test that decreasing received_qty fails when physical_qty would go negative."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
            received_qty=10,
            updated_qty=10,
        )

        ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            company=self.company,
            incoming_qty=0,
            physical_qty=3,
        )

        po.refresh_from_db()

        data = {
            "status": PurchaseOrder.POStatus.DELIVERED,
            "order_details": [
                {
                    "id": str(detail.id),
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 10,
                    "received_qty": 5,
                    "updated_qty": 10,
                    "received_date": str(date.today() + timedelta(days=1)),
                }
            ],
        }

        with patch("apps.purchasing.serializers.compress_pdf_file", return_value=None):
            try:
                self.service.update_purchase_order(po, data)
            except Exception as e:
                error_msg = str(e)
                self.assertIn("order_details", str(e))
                self.assertIn("Physical qty", error_msg)
                self.assertIn("(3)", error_msg)
                self.assertIn("(5)", error_msg)
                return

        self.fail("Exception not raised")

    def test_decrease_received_qty_fails_when_insufficient_cogs_remaining_qty(self):
        """Test that decreasing received_qty fails when COGS remaining_qty is insufficient."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=10,
            received_qty=10,
            updated_qty=10,
        )

        ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            company=self.company,
            incoming_qty=0,
            physical_qty=10,
        )

        po.refresh_from_db()

        ProductCogsFactory(
            company=self.company,
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            reference_number=po.purchase_order_number,
            price_rmb=Decimal("10.0000"),
            exchange_rate=2200,
            cogs_amount=22000,
            original_qty=10,
            remaining_qty=3,
        )

        data = {
            "status": PurchaseOrder.POStatus.DELIVERED,
            "order_details": [
                {
                    "id": str(detail.id),
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 10,
                    "received_qty": 5,
                    "updated_qty": 10,
                    "received_date": str(date.today() + timedelta(days=1)),
                }
            ],
        }

        with patch("apps.purchasing.serializers.compress_pdf_file", return_value=None):
            try:
                self.service.update_purchase_order(po, data)
            except Exception as e:
                error_msg = str(e)
                self.assertIn("order_details", str(e))
                self.assertIn("COGS remaining_qty", error_msg)
                self.assertIn("(3)", error_msg)
                self.assertIn("(5)", error_msg)
                return

        self.fail("Exception not raised")

    def test_update_received_qty_equals_ordered_qty(self):
        """Test updating received_qty equals ordered_qty on purchase_order_detail."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=50,
            unit_price_foreign=Decimal("10"),
        )

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 100,
                            "unit_price_foreign": Decimal("10"),
                            "received_date": str(date.today() + timedelta(days=1)),
                        }
                    ],
                },
            )

        detail.refresh_from_db()
        self.assertEqual(detail.received_qty, 100)
        self.assertEqual(detail.updated_qty, 100)
        self.assertEqual(detail.ordered_qty, 100)
