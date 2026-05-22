from rest_framework import serializers

from core.models import Company, Marketplace, MarketplaceConnection, UserProfile


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class MarketplaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketplace
        fields = "__all__"


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["company_id", "role"]


class MarketplaceConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceConnection
        fields = [
            "id",
            "company",
            "platform",
            "display_name",
            "is_active",
            "shopee_shop_id",
            "tiktok_shop_id",
            "cdate",
            "udate",
        ]
        read_only_fields = ["company"]
