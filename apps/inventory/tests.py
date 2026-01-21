# apps/inventory/tests/test_api.py
from rest_framework.test import APITestCase

from apps.inventory.factories import CategoryFactory
from apps.inventory.models import Product, ProductVariant
from core.factories import CompanyFactory, MarketplaceFactory


class InventoryAPITest(APITestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.category = CategoryFactory(company=self.company)
        self.marketplace = MarketplaceFactory()

    def test_create_product(self):
        payload = {
            "company_id": str(self.company.id),
            "category_id": str(self.category.id),
            "name": "Kemeja Batik Pria Premium",
            "description": "Batik Slimfit bahan katun halus, nyaman untuk kerja maupun acara formal.",
            "variant_options": [{"name": "Warna", "order": 1}, {"name": "Size", "order": 2}],
            "specifications": {
                "Merek": "Tidak ada merek",
                "Bahan": ["Katun", "Bulu Domba"],
                "Motif": ["Batik", "Kotak-kotak"],
                "Negara_Asal": "Indonesia",
            },
            "weight": 300,
            "length": 25,
            "width": 20,
            "height": 3,
            "variants": [
                {
                    "name": "Batik Premium - Navy - L",
                    "sku_variant_code": "1",
                    "variant_values": {"1": "Navy", "2": "L"},
                    "base_price": 180000,
                    "marketplace_listings": [
                        {
                            "marketplace_id": str(self.marketplace.id),
                            "selling_price": 210000,
                            "discounted_price": 195000,
                        }
                    ],
                },
                {
                    "name": "Batik Premium - Navy - XL",
                    "sku_variant_code": "2",
                    "variant_values": {"1": "Navy", "2": "XL"},
                    "base_price": 185000,
                    "marketplace_listings": [
                        {
                            "marketplace_id": str(self.marketplace.id),
                            "selling_price": 215000,
                        }
                    ],
                },
            ],
        }
        response = self.client.post("/product/", payload, format="json")
        if response.status_code == 400:
            print(f"\n❌ Validation Errors: {response.data}")

        # Verify result
        self.assertEqual(response.status_code, 201)

        # Check if the mock actually worked
        product = Product.objects.first()
        variant = ProductVariant.objects.first()

        print(f"Generated SKU: {product.sku_code}")
        print(f"Generated Variant SKU: {variant.sku_variant_code}")

        self.assertTrue(product.sku_code.startswith(self.category.category_code))
        self.assertEqual(variant.sku_variant_code, f"{product.sku_code}-NAVY-L")
