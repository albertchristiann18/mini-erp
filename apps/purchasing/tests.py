from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.purchasing.models import PurchaseOrder
from apps.purchasing.services.purchasing_service import PurchaseOrderService
from core.factories import (
    CategoryFactory,
    CompanyFactory,
    ProductFactory,
    ProductVariantFactory,
    PurchaseOrderDetailFactory,
    PurchaseOrderFactory,
    WarehouseFactory,
)


class PurchaseOrderTest(TestCase):
    """Simple test cases for Purchase Orders"""

    def setUp(self):
        """Set up test client and test data"""
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
            "total_qty": 100,
            "total_amount": 1000000,
            "order_details": [
                {
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 100,
                    "unit_price_base": 10000,
                    "total_price_base": 1000000,
                }
            ],
        }

        response = self.client.post("/purchase-order/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        purchase_order = PurchaseOrder.objects.last()
        self.assertTrue(purchase_order.purchase_order_number.startswith("PO-2026-"))

    def test_update_po(self):
        """Update a PO"""
        po = PurchaseOrderFactory(warehouse=self.warehouse, company=self.company)

        payload = {
            "warehouse_id": str(self.warehouse.id),
            "supplier_name": "Updated Supplier",
            "total_qty": 200,
        }

        response = self.client.put(f"/purchase-order/{po.id}/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase_order = PurchaseOrder.objects.last()
        self.assertEqual(purchase_order.supplier_name, "Updated Supplier")
        self.assertEqual(purchase_order.total_qty, 200)


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
            "total_qty": 100,
            "total_amount": 1000000,
            "order_details": [
                {
                    "product_variant_id": str(self.product_variant.id),
                    "ordered_qty": 100,
                    "unit_price_base": 10000,
                }
            ],
        }

        self.service.create_purchase_order(data)

        po = PurchaseOrder.objects.last()
        self.assertIsNotNone(po.purchase_order_number)
        self.assertEqual(po.status, PurchaseOrder.POStatus.DRAFT)
        self.assertEqual(po.order_details.count(), 1)

    def test_create_purchase_order_without_details_raises_error(self):
        """Test that creating PO without order_details raises ValidationError"""
        data = {
            "purchase_order_number": "PO-2026-002",
            "warehouse_id": str(self.warehouse.id),
            "company_id": str(self.company.id),
            "supplier_name": "Test Supplier",
            "total_qty": 100,
            "total_amount": 1000000,
        }

        with self.assertRaises(ValidationError) as context:
            self.service.create_purchase_order(data)

        self.assertIn("At least one order detail is required", str(context.exception))

    def test_update_po_draft_to_ordered_without_invoice_raises_error(self):
        """Test that transitioning DRAFT to ORDERED without invoice raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )

        data = {"status": PurchaseOrder.POStatus.ORDERED}

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(po, data)

        self.assertIn("please upload the invoice file", str(context.exception))

    def test_update_po_ordered_to_shipped_without_delivery_order_number_raises_error(self):
        """Test that transitioning ORDERED to SHIPPED without DO number raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )

        data = {"status": PurchaseOrder.POStatus.SHIPPED}

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(po, data)

        self.assertIn("please provide the delivery order number", str(context.exception))

    def test_update_po_ordered_to_shipped_without_delivery_order_file_raises_error(self):
        """Test that transitioning ORDERED to SHIPPED without DO file raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
            delivery_order_number="DO-001",
        )

        data = {"status": PurchaseOrder.POStatus.SHIPPED}

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(po, data)

        self.assertIn("please upload the delivery order file", str(context.exception))

    def test_update_po_shipped_to_delivered_without_invoice_raises_error(self):
        """Test that transitioning SHIPPED to DELIVERED without DO invoice raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
            delivery_order_number="DO-001",
        )

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
            data = {"status": PurchaseOrder.POStatus.DELIVERED}

            with self.assertRaises(ValidationError) as context:
                self.service.update_purchase_order(po, data)

            self.assertIn("please upload the delivery order invoice file", str(context.exception))

    def test_update_po_invalid_status_transition_raises_error(self):
        """Test that invalid status transition raises error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.DRAFT,
        )

        data = {"status": PurchaseOrder.POStatus.DELIVERED}

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(po, data)

        self.assertIn("Cannot transition", str(context.exception))

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

    def test_update_po_raises_error_for_nonexistent_detail(self):
        """Test that updating non-existent detail raises error"""
        from uuid import uuid4

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

        with self.assertRaises(ValidationError) as context:
            self.service.update_purchase_order(po, data)

        self.assertIn("not found", str(context.exception))
