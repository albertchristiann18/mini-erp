from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.factories import (
    CategoryFactory,
    CompanyFactory,
    ProductFactory,
    ProductVariantFactory,
    ProductVariantWarehouseFactory,
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

    def test_decrease_received_qty_fails_when_physical_qty_insufficient(self):
        """Test that decreasing received_qty fails when physical qty already sold."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=10,
            updated_qty=10,
        )

        ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            incoming_qty=90,
            physical_qty=3,
        )

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            with self.assertRaises(ValidationError) as context:
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

        self.assertIn("Cannot decrease received_qty", str(context.exception))

    def test_received_qty_exceeds_ordered_requires_remarks(self):
        """Test that received_qty > ordered_qty requires remarks."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=10,
            updated_qty=10,
        )

        ProductVariantWarehouseFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            incoming_qty=90,
            physical_qty=10,
        )

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            with self.assertRaises(ValidationError) as context:
                self.service.update_purchase_order(
                    po,
                    {
                        "status": PurchaseOrder.POStatus.DELIVERED,
                        "order_details": [
                            {
                                "id": str(detail.id),
                                "product_variant_id": str(self.product_variant.id),
                                "ordered_qty": 100,
                                "received_qty": 150,
                                "updated_qty": 10,
                                "received_date": str(date.today() + timedelta(days=1)),
                            }
                        ],
                    },
                )

        self.assertIn("Remarks is required", str(context.exception))

    def test_update_po_detail_not_found_in_non_draft_status(self):
        """Test that updating non-existent detail fails in non-DRAFT status."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )
        PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        po.refresh_from_db()

        with patch("apps.purchasing.serializers.compress_pdf_file"):
            with self.assertRaises(ValidationError) as context:
                self.service.update_purchase_order(
                    po,
                    {
                        "order_details": [
                            {
                                "id": str(uuid4()),
                                "ordered_qty": 50,
                            }
                        ]
                    },
                )

        self.assertIn("Detail with id", str(context.exception))

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

    def test_update_po_draft_replace_one_detail_with_new_product(self):
        """Test replacing one existing detail with a new product in DRAFT status.

        Scenario: PO has item A and item B. We want to replace item B with item C.
        Result should be: item A and item C.
        """
        product_b = ProductFactory(category=self.category, company=self.company)
        product_variant_b = ProductVariantFactory(product=product_b)

        product_c = ProductFactory(category=self.category, company=self.company)
        product_variant_c = ProductVariantFactory(product=product_c)

        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )
        detail_a = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )
        detail_b = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=product_variant_b, ordered_qty=75
        )

        data = {
            "order_details": [
                {
                    "id": str(detail_a.id),
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 50,
                },
                {
                    "product_variant_id": str(product_variant_c.id),
                    "ordered_qty": 100,
                },
            ]
        }

        self.service.update_purchase_order(po, data)

        po.refresh_from_db()
        self.assertEqual(po.order_details.count(), 2)
        self.assertTrue(po.order_details.filter(id=detail_a.id).exists())
        self.assertFalse(po.order_details.filter(id=detail_b.id).exists())
        self.assertTrue(
            po.order_details.filter(product_variant=product_variant_c, ordered_qty=100).exists()
        )

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

    def test_update_po_delivered_to_completed_partial_requires_remarks(self):
        """Test that transitioning to COMPLETED with partial delivery requires remarks."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DELIVERED,
            delivery_date=date.today(),
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=80,
            updated_qty=80,
        )

        po.refresh_from_db()

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.COMPLETED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 80,
                            "updated_qty": 80,
                        }
                    ],
                },
            )

        self.assertIn("Remarks is required", str(context.exception))

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

    def test_received_qty_cannot_be_filled_if_status_not_shipped_or_delivered(self):
        """Test that received_qty cannot be filled when status is not SHIPPED or DELIVERED"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            purchase_order_invoice_file="invoice.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            supplier_name="Supplier",
            forwarder_name="Forwarder",
            shop_services="service",
            commission_fee_pct=Decimal("10"),
            delivery_fee=100,
        )

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.ORDERED,
                "order_details": [
                    {
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 100,
                        "received_qty": 50,
                        "unit_price_foreign": Decimal("10"),
                    }
                ],
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)
        self.assertIn("received_qty", str(serializer.errors["order_details"]))

    def test_received_qty_allowed_when_status_is_shipped(self):
        """Test that received_qty can be filled when status is SHIPPED"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            exchange_rate=2200,
            delivery_order_number="DO-001",
            delivery_order_file="existing_file.pdf",
            shipping_fee_per_cbm=100,
            cbm=Decimal("1"),
            weight=Decimal("10"),
        )

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.SHIPPED,
                "order_details": [
                    {
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 100,
                        "received_qty": 50,
                        "unit_price_foreign": Decimal("10"),
                    }
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_received_qty_allowed_when_status_is_delivered(self):
        """Test that received_qty can be filled when status is DELIVERED"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            exchange_rate=2200,
            delivery_order_invoice_file="existing_file.pdf",
        )

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.DELIVERED,
                "order_details": [
                    {
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 100,
                        "received_qty": 50,
                        "unit_price_foreign": Decimal("10"),
                    }
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_cannot_add_new_details_when_not_draft(self):
        """Test that adding new details fails when status is not DRAFT"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            exchange_rate=2200,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        product2 = ProductFactory(category=self.category, company=self.company)
        product_variant2 = ProductVariantFactory(product=product2)

        po.refresh_from_db()

        serializer = self._create_serializer(
            po,
            {
                "order_details": [
                    {
                        "id": str(detail.id),
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 100,
                    },
                    {
                        "product_variant_id": str(product_variant2.id),
                        "ordered_qty": 50,
                        "unit_price_foreign": Decimal("10"),
                    },
                ],
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)
        self.assertIn("Cannot add new details", str(serializer.errors["order_details"]))

    def test_cannot_change_ordered_qty_from_draft_to_ordered(self):
        """Test that ordered_qty cannot be changed when transitioning from DRAFT to ORDERED"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
            exchange_rate=2200,
            forwarder_name="Test Forwarder",
            shop_services="Test Service",
            commission_fee_pct=Decimal("10"),
            delivery_fee=100,
            purchase_order_invoice_file="invoice.pdf",
            invoice_number="INV-001",
            invoice_date=date.today(),
            supplier_name="Supplier",
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_foreign=Decimal("10"),
        )

        po.refresh_from_db()

        serializer = self._create_serializer(
            po,
            {
                "status": PurchaseOrder.POStatus.ORDERED,
                "order_details": [
                    {
                        "id": str(detail.id),
                        "product_variant_id": str(self.product_variant.id),
                        "ordered_qty": 150,
                        "unit_price_foreign": Decimal("10"),
                    },
                ],
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)
        self.assertIn("ordered_qty", str(serializer.errors["order_details"]))
