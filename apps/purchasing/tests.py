from datetime import date
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory
from rest_framework.test import APIClient

from apps.purchasing.models import PurchaseOrder, PurchaseOrderDetail
from apps.purchasing.serializers import PurchaseOrderUpdateSerializer
from apps.purchasing.services.purchasing_service import PurchaseOrderService
from apps.inventory.models import ProductCogs, ProductVariantWarehouse, StockMovement
from core.factories import (
    CategoryFactory,
    CompanyFactory,
    ProductCogsFactory,
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
        product_variant2 = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_base=20000,
        )

        data = {
            "order_details": [
                {
                    "id": str(detail1.id),
                    "ordered_qty": 50,
                },
                {
                    "id": str(product_variant2.id),
                    "ordered_qty": 100,
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
            unit_price_base=30000,
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

    def test_update_po_non_draft_add_new_detail_raises_error(self):
        """Test that adding new detail to PO in non-DRAFT status raises validation error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )
        new_detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
        )

        rf = APIRequestFactory()
        request = rf.put(f"/purchase-order/{po.id}/")
        serializer = PurchaseOrderUpdateSerializer(
            po,
            data={
                "order_details": [
                    {
                        "id": str(detail.id),
                        "ordered_qty": 50,
                    },
                    {
                        "id": str(new_detail.id),
                        "ordered_qty": 100,
                    },
                ]
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)

    def test_update_po_non_draft_remove_detail_raises_error(self):
        """Test that removing detail from PO in non-DRAFT status raises validation error"""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.ORDERED,
        )
        detail1 = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=50
        )
        detail2 = PurchaseOrderDetailFactory(
            purchase_order=po, product_variant=self.product_variant, ordered_qty=75
        )

        factory = APIRequestFactory()
        request = factory.put(f"/purchase-order/{po.id}/")
        serializer = PurchaseOrderUpdateSerializer(
            po,
            data={
                "order_details": [
                    {
                        "id": str(detail1.id),
                        "ordered_qty": 50,
                    },
                ]
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order_details", serializer.errors)

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

    def test_update_po_delivered_partial_received_qty(self):
        """Test updating received_qty partially while in DELIVERED status."""
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

        mock_file = MagicMock()
        with patch(
            "apps.purchasing.services.purchasing_service.compress_pdf_file", return_value=mock_file
        ):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.ORDERED,
                    "purchase_order_invoice_file": mock_file,
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()

        self.assertEqual(po.status, PurchaseOrder.POStatus.ORDERED)
        self.assertEqual(detail.updated_qty, 100)

        pvw = ProductVariantWarehouse.objects.get(
            product_variant=self.product_variant, warehouse=self.warehouse
        )
        self.assertEqual(pvw.incoming_qty, 100)
        self.assertEqual(pvw.physical_qty, 0)

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
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
                            "received_date": (timezone.now() + timedelta(days=1)).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        pvw.refresh_from_db()

        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)
        self.assertEqual(detail.updated_qty, 50)
        self.assertEqual(detail.received_qty, 50)
        self.assertEqual(pvw.incoming_qty, 0)
        self.assertEqual(pvw.physical_qty, 50)

        incoming_after_first_delivery = pvw.incoming_qty

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 75,
                            "updated_qty": 50,
                            "received_date": (timezone.now() + timedelta(days=2)).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        pvw.refresh_from_db()

        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)
        self.assertEqual(detail.updated_qty, 75)
        self.assertEqual(detail.received_qty, 75)

        self.assertEqual(
            pvw.incoming_qty,
            incoming_after_first_delivery,
            "incoming_qty should not change on subsequent received_qty updates",
        )
        self.assertEqual(
            pvw.physical_qty,
            75,
            "physical_qty should be updated by the diff (75 - 50 = 25)",
        )

    def test_update_po_delivered_decrease_received_qty(self):
        """Test decreasing received_qty while in DELIVERED status."""
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

        mock_file = MagicMock()
        with patch(
            "apps.purchasing.services.purchasing_service.compress_pdf_file", return_value=mock_file
        ):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.ORDERED,
                    "purchase_order_invoice_file": mock_file,
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
            self.service.update_purchase_order(
                po,
                {
                    "status": PurchaseOrder.POStatus.DELIVERED,
                    "order_details": [
                        {
                            "id": str(detail.id),
                            "product_variant_id": str(self.product_variant.id),
                            "ordered_qty": 100,
                            "received_qty": 10,
                            "received_date": (timezone.now() + timedelta(days=1)).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        pvw = ProductVariantWarehouse.objects.get(
            product_variant=self.product_variant, warehouse=self.warehouse
        )

        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)
        self.assertEqual(detail.updated_qty, 10)
        self.assertEqual(detail.received_qty, 10)
        self.assertEqual(pvw.incoming_qty, 90)
        self.assertEqual(pvw.physical_qty, 10)

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
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
                            "received_date": (timezone.now() + timedelta(days=2)).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        pvw.refresh_from_db()

        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)
        self.assertEqual(detail.updated_qty, 5)
        self.assertEqual(detail.received_qty, 5)

        self.assertEqual(
            pvw.incoming_qty,
            95,
            "incoming_qty should increase by ordered_qty - received_qty (100 - 5 = 95)",
        )
        self.assertEqual(
            pvw.physical_qty,
            5,
            "physical_qty should be updated by the diff (5 - 10 = -5)",
        )

    def test_update_po_delivered_creates_cogs(self):
        """Test that transitioning to DELIVERED creates COGS records."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            unit_price_base=15000,
        )

        initial_cogs_count = ProductCogs.objects.count()

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
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
                            "unit_price_base": 15000,
                            "received_date": (timezone.now()).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant, warehouse=self.warehouse
        )
        self.assertEqual(cogs.count(), initial_cogs_count + 1)

        cogs_record = cogs.first()
        self.assertIsNotNone(cogs_record)
        self.assertEqual(cogs_record.original_qty, 80)
        self.assertEqual(cogs_record.remaining_qty, 80)
        self.assertEqual(cogs_record.cogs_amount, 80 * 15000)

    def test_update_po_delivered_updates_cogs_on_qty_change(self):
        """Test that changing received_qty in DELIVERED status updates COGS."""
        po = PurchaseOrderFactory(
            warehouse=self.warehouse,
            company=self.company,
            status=PurchaseOrder.POStatus.SHIPPED,
        )
        detail = PurchaseOrderDetailFactory(
            purchase_order=po,
            product_variant=self.product_variant,
            ordered_qty=100,
            received_qty=50,
            updated_qty=50,
            unit_price_base=15000,
        )

        initial_cogs_count = ProductCogs.objects.count()

        ProductCogsFactory(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            purchase_order_detail=detail,
            purchase_date=date.today(),
            price_rmb=15000,
            exchange_rate=1,
            cogs_amount=50 * 15000,
            original_qty=50,
            remaining_qty=50,
        )

        with patch("apps.purchasing.services.purchasing_service.compress_pdf_file"):
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
                            "unit_price_base": 15000,
                            "received_date": (timezone.now()).isoformat(),
                        }
                    ],
                },
            )

        po.refresh_from_db()
        detail.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.POStatus.DELIVERED)

        cogs = ProductCogs.objects.filter(
            product_variant=self.product_variant,
            warehouse=self.warehouse,
            purchase_order_detail=detail,
        ).first()
        self.assertIsNotNone(cogs)
        self.assertEqual(cogs.original_qty, 80)
        self.assertEqual(cogs.remaining_qty, 80)
        self.assertEqual(cogs.cogs_amount, 80 * 15000)

    def test_update_po_completed_does_not_create_cogs(self):
        """Test that transitioning to COMPLETED does not create new COGS."""
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
            unit_price_base=15000,
        )

        initial_cogs_count = ProductCogs.objects.count()

        self.service.update_purchase_order(
            po,
            {"status": PurchaseOrder.POStatus.COMPLETED},
        )

        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.POStatus.COMPLETED)

        cogs_count = ProductCogs.objects.filter(
            product_variant=self.product_variant, warehouse=self.warehouse
        ).count()
        self.assertEqual(cogs_count, initial_cogs_count, "COGS should not be created on COMPLETED")
