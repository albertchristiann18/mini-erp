# factories.py
import factory

from core.models import Company, Marketplace


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = "Test Company"


class MarketplaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Marketplace

    name = "Default Marketplace"
