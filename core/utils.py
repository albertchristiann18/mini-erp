from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List

from ulid.api.api import Api
from ulid.providers import DEFAULT


def generate_ulid() -> Any:
    """Generate a new ULID for use as default in Django models."""
    return Api(DEFAULT).new()


def round_decimal(value: Any, places: int = 3) -> Decimal:
    # This is 100% safe for ERP use
    return Decimal(str(value)).quantize(Decimal(f"1.{'0' * places}"), rounding=ROUND_HALF_UP)


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
                    "expeditions": [{"code": "spx_hemat", "name": "SPX Hemat", "is_active": False}]
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


def is_valid_status_transition(
    current_status: str,
    new_status: str,
    status_map: Dict[str, List[str]],
) -> bool:
    """
    Check if a status transition is valid.

    Args:
        current_status: The current status
        new_status: The desired new status
        status_map: Dictionary mapping current status to list of allowed next statuses
            Example:
            {
                "DRAFT": ["ORDERED"],
                "ORDERED": ["SHIPPED", "DRAFT"],
                "SHIPPED": ["DELIVERED"],
                "DELIVERED": ["COMPLETED"],
                "COMPLETED": [],
            }

    Returns:
        True if transition is valid, False otherwise
    """
    allowed = status_map.get(current_status, [])
    return new_status in allowed
