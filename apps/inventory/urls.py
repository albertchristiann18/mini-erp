from rest_framework.routers import DefaultRouter

from apps.inventory import views

urlpatterns = []

router = DefaultRouter()
router.register(r"category", views.CategoryViewSet)
router.register(r"product", views.ProductViewSet)
router.register(r"warehouse", views.WarehouseViewSet)

urlpatterns += router.urls
