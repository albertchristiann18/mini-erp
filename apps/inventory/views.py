from typing import Any, Type

from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.inventory.models import Category, Product, ProductPhoto, Warehouse
from apps.inventory.serializers import (
    CategorySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProductPhotoSerializer,
    ProductVariantStockSerializer,
    WarehouseSerializer,
)
from apps.inventory.services import product_service
from apps.inventory.constants.categories import MASTER_CATEGORY
from apps.inventory.services.bulk_inventory_service import BulkInventoryService
from core.permissions import IsStaffOrReadOnly


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).all()
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True).all()
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) | models.Q(sku_code__icontains=search)
            )
        return qs

    def get_serializer_class(self) -> Type[Serializer]:
        if self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        is_many = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        services = product_service.ProductService()
        services.create_product_with_variants(validated_data)

        return Response(status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="photos", parser_classes=[MultiPartParser, FormParser])
    def upload_photo(self, request: Request, pk: str | None = None) -> Response:
        product = self.get_object()
        if product.photos.count() >= 9:
            return Response({"error": "Maximum 9 photos allowed"}, status=400)
        image = request.FILES.get("image")
        if not image:
            return Response({"error": "No image provided"}, status=400)
        order = product.photos.count()
        is_primary = order == 0
        photo = ProductPhoto.objects.create(
            product=product, company=product.company, image=image, order=order, is_primary=is_primary
        )
        return Response(ProductPhotoSerializer(photo).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"photos/(?P<photo_id>[^/.]+)")
    def delete_photo(self, request: Request, pk: str | None = None, photo_id: str | None = None) -> Response:
        photo = get_object_or_404(ProductPhoto, id=photo_id, product_id=pk)
        photo.delete()
        for i, p in enumerate(ProductPhoto.objects.filter(product_id=pk).order_by("order")):
            p.order = i
            p.is_primary = i == 0
            p.save()
        return Response(status=204)

    @action(detail=True, methods=["patch"], url_path=r"photos/(?P<photo_id>[^/.]+)/reorder")
    def reorder_photos(self, request: Request, pk: str | None = None, photo_id: str | None = None) -> Response:
        photo_ids = request.data.get("photo_ids", [])
        for i, pid in enumerate(photo_ids):
            ProductPhoto.objects.filter(id=pid, product_id=pk).update(order=i, is_primary=(i == 0))
        photos = ProductPhoto.objects.filter(product_id=pk).order_by("order")
        return Response(ProductPhotoSerializer(photos, many=True).data)

    @action(detail=False, methods=["post"], url_path="bulk_create")
    def bulk_create_products(self, request: Request) -> Response:
        if not isinstance(request.data, list):
            return Response({"error": "Expected JSON array"}, status=400)
        serializer = ProductCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        services = product_service.ProductService()
        services.create_product_with_variants(serializer.validated_data)
        return Response({"created": len(request.data), "errors": []}, status=201)


class ProductVariantStockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns variants with their stock per warehouse.
    Query params:
      - warehouse: warehouse ID (optional) — if provided, returns physical_qty for that warehouse
      - search: filter by variant name, sku_variant_code, or parent product name
    """
    permission_classes = [IsStaffOrReadOnly]
    serializer_class = ProductVariantStockSerializer

    def get_queryset(self):
        from apps.inventory.models import ProductVariant
        qs = ProductVariant.objects.filter(is_active=True).select_related('product', 'product__category')
        search = self.request.query_params.get('search')
        if search:
            from django.db import models as db_models
            qs = qs.filter(
                db_models.Q(name__icontains=search) |
                db_models.Q(sku_variant_code__icontains=search) |
                db_models.Q(product__name__icontains=search)
            )
        return qs.order_by('product__name', 'name')


class MasterCategoryViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request: Request) -> Response:
        return Response(MASTER_CATEGORY)


class InventoryBulkViewSet(viewsets.ViewSet):
    permission_classes = [IsStaffOrReadOnly]

    @action(detail=False, methods=["post"], url_path="bulk_update")
    def bulk_update(self, request: Request) -> Response:
        updates = request.data
        if not isinstance(updates, list):
            return Response({"error": "Expected JSON array"}, status=400)
        result = BulkInventoryService.bulk_update(updates)
        return Response(result, status=200)

    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request: Request) -> Response:
        """
        Single variant stock adjustment.
        Body: { variant_id, warehouse_id, type: 'add'|'min'|'set', qty: int }
        """
        variant_id = request.data.get('variant_id')
        warehouse_id = request.data.get('warehouse_id')
        adj_type = request.data.get('type')
        qty = request.data.get('qty')

        if not all([variant_id, warehouse_id, adj_type, qty is not None]):
            return Response({'error': 'variant_id, warehouse_id, type, qty are required'}, status=400)
        if adj_type not in ('add', 'min', 'set'):
            return Response({'error': 'type must be add, min, or set'}, status=400)

        result = BulkInventoryService.bulk_update([{
            'variant_id': variant_id,
            'warehouse_id': warehouse_id,
            'qty': qty,
            'type': adj_type,
        }])
        return Response(result, status=200)


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True).all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsStaffOrReadOnly]
