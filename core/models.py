from django.db import models
from django_ulid.models import ULIDField

from core.utils import generate_ulid, get_default_shipping_config


class TimeStampedModel(models.Model):
    class Meta(object):
        abstract = True

    cdate = models.DateTimeField(auto_now_add=True)
    udate = models.DateTimeField(auto_now=True)


class Company(TimeStampedModel):
    id = ULIDField(primary_key=True, default=generate_ulid, editable=False, db_column="company_id")
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tax_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name}"


class DefaultModel(TimeStampedModel):
    class Meta(object):
        abstract = True

    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column="company_id")


class Marketplace(TimeStampedModel):
    id = ULIDField(
        primary_key=True, default=generate_ulid, editable=False, db_column="marketplace_id"
    )
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    connected_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # New Shipping Configuration field
    shipping_config = models.JSONField(
        default=get_default_shipping_config,
        blank=True,
        help_text="Stores marketplace-specific shipping and insurance settings",
    )
