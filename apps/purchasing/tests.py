from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.purchasing.models import PurchaseOrder
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
            "supplier_name": "Updated Supplier",
            "total_qty": 200,
        }

        response = self.client.put(f"/purchase-order/{po.id}/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase_order = PurchaseOrder.objects.last()
        self.assertEqual(purchase_order.supplier_name, "Updated Supplier")
        self.assertEqual(purchase_order.total_qty, 200)
