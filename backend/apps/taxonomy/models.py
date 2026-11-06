"""Reference data used to describe and search mentors. Seeded by a data migration."""

from django.db import models

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    """A career area / industry, e.g. Technology or Finance. Shown as "industries" in the UI."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Profession(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="professions"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Language(models.Model):
    """Languages a mentor offers sessions in (ISO 639-1 codes)."""

    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
