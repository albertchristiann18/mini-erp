from typing import Any

from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.inventory.models import Category, Product, Warehouse
from apps.inventory.serializers import (
    CategorySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    WarehouseSerializer,
)
from apps.inventory.services import product_service


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True).all()

    def get_serializer_class(self) -> Any:
        if self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        is_many = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        ProductService = product_service.ProductService()
        ProductService.create_product_with_variants(validated_data)

        return Response(status=status.HTTP_201_CREATED)


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True).all()
    serializer_class = WarehouseSerializer
