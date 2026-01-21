from django.db import models
from django_ulid.models import ULIDField, default


class TimeStampedModel(models.Model):
    class Meta(object):
        abstract = True

    cdate = models.DateTimeField(auto_now_add=True)
    udate = models.DateTimeField(auto_now=True)


class Company(TimeStampedModel):
    id = ULIDField(primary_key=True, default=default, editable=False, db_column="company_id")
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
    id = ULIDField(primary_key=True, default=default, editable=False, db_column="marketplace_id")
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    connected_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    @staticmethod
    def get_default_shipping_config() -> dict:
        return {
            "insurance": {"is_required": False, "fee_type": "percentage"},
            "general": {
                "reguler": {
                    "cod": True,
                    "expeditions": [
                        {
                            "code": "anteraja_reguler",
                            "name": "Anteraja Reguler",
                            "is_active": False,
                        },
                        {"code": "id_express", "name": "ID Express", "is_active": False},
                        {"code": "jne", "name": "JNE Reguler", "is_active": False},
                        {"code": "ninja_xpress", "name": "Ninja Xpress", "is_active": False},
                        {"code": "pos_reguler", "name": "Pos Reguler", "is_active": False},
                        {"code": "sicepat", "name": "SiCepat REG", "is_active": False},
                        {"code": "jnt", "name": "J&T Express", "is_active": False},
                        {"code": "express", "name": "Express", "is_active": False},
                    ],
                },
                "instant": {
                    "cod": False,
                    "expeditions": [
                        {"code": "grab", "name": "GrabExpress", "is_active": False},
                        {"code": "gojek", "name": "GoSend Instant", "is_active": False},
                    ],
                },
                "instant_priority": {
                    "cod": False,
                    "expeditions": [
                        {
                            "code": "grab",
                            "name": "GrabExpress Instant Prioritas",
                            "is_active": False,
                        },
                        {"code": "gojek", "name": "GoSend Instant Prioritas", "is_active": False},
                    ],
                },
                "cargo": {
                    "cod": False,
                    "expeditions": [
                        {"code": "anteraja_cargo", "name": "Anteraja Cargo", "is_active": False},
                        {
                            "code": "anteraja_economy",
                            "name": "Anteraja Economy",
                            "is_active": False,
                        },
                        {"code": "jnt", "name": "J&T Cargo", "is_active": False},
                        {"code": "jne", "name": "JNE Trucking (JTR)", "is_active": False},
                        {"code": "sentral_cargo", "name": "Sentral Cargo", "is_active": False},
                        {"code": "sicepat_gokil", "name": "Sicepat Gokil", "is_active": False},
                        {"code": "sicepat_halu", "name": "SiCepat Halu", "is_active": False},
                        {"code": "express_eco", "name": "Express Eco", "is_active": False},
                    ],
                },
                "sameday": {
                    "cod": False,
                    "expeditions": [
                        {"code": "anteraja", "name": "Anteraja Sameday", "is_active": False},
                        {"code": "grab", "name": "GrabExpress Sameday", "is_active": False},
                        {"code": "gojek", "name": "GoSend Same Day", "is_active": False},
                    ],
                },
                "nextday": {
                    "cod": False,
                    "expeditions": [
                        {"code": "jne", "name": "JNE YES", "is_active": False},
                        {"code": "sicepat", "name": "Sicepat BEST", "is_active": False},
                    ],
                },
            },
            "marketplaces": {
                "Shopee": {
                    "reguler": {
                        "expeditions": [
                            {"code": "spx_standard", "name": "SPX Standard", "is_active": False}
                        ]
                    },
                    "cargo": {
                        "expeditions": [
                            {"code": "spx_hemat", "name": "SPX Hemat", "is_active": False}
                        ]
                    },
                    "instant": {
                        "expeditions": [
                            {"code": "spx_instant", "name": "SPX Instant", "is_active": False}
                        ]
                    },
                    "instant_priority": {
                        "expeditions": [
                            {
                                "code": "spx_instant_prio",
                                "name": "SPX Instant Prioritas",
                                "is_active": False,
                            }
                        ]
                    },
                    "sameday": {
                        "expeditions": [
                            {"code": "spx_sameday", "name": "SPX Sameday", "is_active": False}
                        ]
                    },
                },
                "Tokopedia_TikTok": {"use_general_config": True},
            },
        }

    # New Shipping Configuration field
    shipping_config = models.JSONField(
        default=get_default_shipping_config,
        blank=True,
        help_text="Stores marketplace-specific shipping and insurance settings",
    )
