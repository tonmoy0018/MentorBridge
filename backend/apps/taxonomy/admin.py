from django.contrib import admin

from .models import Category, Language, Profession, Skill


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "category"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
