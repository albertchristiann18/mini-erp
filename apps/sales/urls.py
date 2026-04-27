from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales.views import SalesOrderViewSet, SalesReturnViewSet

router = DefaultRouter()
router.register(r"sales-orders", SalesOrderViewSet, basename="sales-order")
router.register(r"sales-returns", SalesReturnViewSet, basename="sales-return")

urlpatterns = [
    path("", include(router.urls)),
]
