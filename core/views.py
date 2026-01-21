from rest_framework import viewsets

from core.models import Company, Marketplace
from core.serializers import CompanySerializer, MarketplaceSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.filter(is_active=True).all()
    serializer_class = CompanySerializer


class MarketplaceViewSet(viewsets.ModelViewSet):
    queryset = Marketplace.objects.filter(is_active=True).all()
    serializer_class = MarketplaceSerializer
