from typing import Any, Type

from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from apps.purchasing.models import PurchaseOrder
from apps.purchasing.serializers import (
    PurchaseOrderCreateSerializer,
    PurchaseOrderListSerializer,
    PurchaseOrderReadSerializer,
    PurchaseOrderUpdateSerializer,
)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    API endpoints for Purchase Orders.
    - GET /purchase-orders/ - List all purchase orders
    - POST /purchase-orders/ - Create purchase order with nested details
    - GET /purchase-orders/{id}/ - Get purchase order details
    - PUT/PATCH /purchase-orders/{id}/ - Update purchase order and details
    """

    queryset = PurchaseOrder.objects.all()
    http_method_names = ["get", "post", "put", "patch"]

    def get_serializer_class(self) -> Type[Serializer]:
        if self.action == "create":
            return PurchaseOrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return PurchaseOrderUpdateSerializer
        elif self.action == "list":
            return PurchaseOrderListSerializer
        else:  # retrieve
            return PurchaseOrderReadSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get list of all Purchase Orders (basic info without details)"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new Purchase Order with nested details"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = serializer.save()
            read_serializer = PurchaseOrderReadSerializer(po)
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Get a Purchase Order with all details"""
        instance = self.get_object()
        serializer = PurchaseOrderReadSerializer(instance)
        return Response(serializer.data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Update Purchase Order and details"""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)

        try:
            po = serializer.save()
            read_serializer = PurchaseOrderReadSerializer(po)
            return Response(read_serializer.data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
