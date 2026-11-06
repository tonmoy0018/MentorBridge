from rest_framework import serializers

from .models import Category, Language, Profession, Skill


class TaxonomyItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class CategorySerializer(serializers.ModelSerializer):
    mentor_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "is_active", "mentor_count"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not hasattr(instance, "mentor_count"):
            data.pop("mentor_count", None)  # only present when counts were requested
        return data


class ProfessionSerializer(serializers.ModelSerializer):
    industry = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)

    class Meta:
        model = Profession
        fields = ["id", "name", "slug", "industry"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "slug"]


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ["code", "name"]


class CountrySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
