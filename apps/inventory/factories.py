import factory

from apps.inventory.models import Category
from core.factories import CompanyFactory


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = "Default Category"
    category_code = "DEF"
    company = factory.SubFactory(CompanyFactory)  # type: ignore[no-untyped-call]
