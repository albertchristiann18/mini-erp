from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import Company, Marketplace, MarketplaceConnection
from core.serializers import CompanySerializer, MarketplaceConnectionSerializer, MarketplaceSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.filter(is_active=True).all()
    serializer_class = CompanySerializer


class MarketplaceViewSet(viewsets.ModelViewSet):
    queryset = Marketplace.objects.filter(is_active=True).all()
    serializer_class = MarketplaceSerializer


class MarketplaceConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = MarketplaceConnectionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            profile = getattr(user, "profile", None)
            if profile:
                return MarketplaceConnection.objects.filter(company=profile.company)
        return MarketplaceConnection.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        profile = getattr(user, "profile", None) if user.is_authenticated else None
        company = profile.company if profile else None
        serializer.save(company=company)

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        conn = self.get_object()
        conn.is_active = not conn.is_active
        conn.save()
        return Response(MarketplaceConnectionSerializer(conn).data)
