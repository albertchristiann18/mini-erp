from typing import Any

from rest_framework import viewsets

from apps.inventory.models import Category, Product, Warehouse
from apps.inventory.serializers import (
    CategorySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    WarehouseSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True).all()

    def get_serializer_class(self) -> Any:
        if self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True).all()
    serializer_class = WarehouseSerializer
