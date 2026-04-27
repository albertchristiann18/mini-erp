from typing import Any, Type

from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.inventory.models import Category, Product, Warehouse
from apps.inventory.serializers import (
    CategorySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    WarehouseSerializer,
)
from apps.inventory.services import product_service
from core.permissions import IsStaffOrReadOnly


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).all()
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True).all()
    permission_classes = [IsStaffOrReadOnly]

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


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True).all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsStaffOrReadOnly]
