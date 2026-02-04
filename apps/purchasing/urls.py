from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchasing.views import PurchaseOrderViewSet

router = DefaultRouter()
router.register(r"purchase-order", PurchaseOrderViewSet, basename="purchase-order")

urlpatterns = [
    path("", include(router.urls)),
]
