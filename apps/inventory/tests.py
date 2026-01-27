# apps/inventory/tests/test_api.py
from rest_framework.test import APITestCase

from apps.inventory.factories import CategoryFactory
from apps.inventory.models import Product, ProductVariant, ProductVariantMarketplace
from core.factories import CompanyFactory, MarketplaceFactory


class InventoryAPITest(APITestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.category = CategoryFactory(company=self.company)
        self.marketplace = MarketplaceFactory()
        self.base_payload = [
            {
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
                        # "sku_variant_code": "1",
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
                        # "sku_variant_code": "2",
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
        ]

    def test_create_product(self):
        response = self.client.post("/product/", self.base_payload, format="json")
        # Verify result
        self.assertEqual(response.status_code, 201)

        # Check if the mock actually worked
        product = Product.objects.last()
        variants = ProductVariant.objects.filter(product=product)
        self.assertTrue(product.sku_code.startswith(self.category.category_code))
        for v in variants:
            self.assertEqual(v.product_id, product.id)
            self.assertIn("NAVY", v.sku_variant_code)

    def test_create_multiple_product(self):
        payload = self.base_payload + [
            {
                "company_id": str(self.company.id),
                "category_id": str(self.category.id),
                "name": "Kemeja Batik Pria Premium B",
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
                        "name": "Batik Premium B - Blue - L",
                        # "sku_variant_code": "1",
                        "variant_values": {"1": "Blue", "2": "L"},
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
                        "name": "Batik Premium B - Blue - XL",
                        # "sku_variant_code": "2",
                        "variant_values": {"1": "Blue", "2": "XL"},
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
        ]
        response = self.client.post("/product/", payload, format="json")
        # Verify result
        self.assertEqual(response.status_code, 201)

        # 1. Verify Database Counts (The most important bulk check)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(ProductVariant.objects.count(), 4)
        # Verify 4 listings (2 per product in your payload)
        from apps.inventory.models import ProductVariantMarketplace

        self.assertEqual(ProductVariantMarketplace.objects.count(), 4)

        # 2. Verify First Product Relationship
        product_a = Product.objects.get(name="Kemeja Batik Pria Premium")
        variants_a = ProductVariant.objects.filter(product=product_a).order_by("name")
        self.assertEqual(variants_a.count(), 2)
        # Check that the SKU correctly combined Parent SKU + Variant values
        self.assertIn(product_a.sku_code, variants_a[0].sku_variant_code)

        # 3. Verify Second Product Relationship (The Global Index Test)
        product_b = Product.objects.get(name="Kemeja Batik Pria Premium B")
        variants_b = ProductVariant.objects.filter(product=product_b).order_by("name")
        self.assertEqual(variants_b.count(), 2)

        # Verify that the variant for Product B is NOT linked to Product A
        # This confirms your global counter logic worked!
        for v in variants_b:
            self.assertEqual(v.product_id, product_b.id)
            self.assertIn("BLUE", v.sku_variant_code)  # Assuming your trigger uppercases it

    def test_create_multiple_products_with_nested_variants_and_listings(self):
        """
        Tests that 2 products with multiple variants and listings
        are correctly mapped and saved in bulk.
        """
        # setup_data would be a fixture or dictionary containing your payload
        payload = self.base_payload + [
            {
                "company_id": str(self.company.id),
                "category_id": str(self.category.id),
                "name": "Kemeja Batik Pria Premium B",
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
                        "name": "Batik Premium B - Blue - L",
                        # "sku_variant_code": "1",
                        "variant_values": {"1": "Blue", "2": "L"},
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
                        "name": "Batik Premium B - Blue - XL",
                        # "sku_variant_code": "2",
                        "variant_values": {"1": "Blue", "2": "XL"},
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
        ]

        response = self.client.post("/product/", payload, format="json")

        # 1. Basic Response Check
        assert response.status_code == 201

        # 2. Verify Database Integrity (Counts)
        assert Product.objects.count() == 2
        assert ProductVariant.objects.count() == 4
        assert ProductVariantMarketplace.objects.count() == 4

        # 3. Verify Specific Mapping (Global Indexing Check)
        # Fetch the second product to ensure it didn't get Product A's variants
        prod_b = Product.objects.get(name="Kemeja Batik Pria Premium B")
        variants_b = ProductVariant.objects.filter(product=prod_b)

        assert variants_b.count() == 2
        for variant in variants_b:
            # Verify the variant names match the 'Blue' logic in payload B
            assert "Blue" in variant.name

            # Verify Marketplace Listings are linked to these specific variants
            listings = ProductVariantMarketplace.objects.filter(product_variant=variant)
            assert listings.exists()
            assert listings.count() == 1

    def test_atomic_rollback_on_failure(self):
        """
        Tests that if data is partially corrupt (e.g., missing marketplace_id),
        NO products are created (Transaction Rollback).
        """
        payload = self.base_payload
        payload[0]["variants"][1]["marketplace_listings"][0]["marketplace_id"] = None

        self.client.post("/product/", payload, format="json")
        assert Product.objects.count() == 0
