from django.urls import path

from . import views

category_urlpatterns = [
    path("", views.CategoryListView.as_view(), name="categories"),
    path("<slug:slug>/", views.CategoryDetailView.as_view(), name="category"),
]

taxonomy_urlpatterns = [
    path("professions/", views.ProfessionListView.as_view(), name="taxonomy-professions"),
    path("skills/", views.SkillListView.as_view(), name="taxonomy-skills"),
    path("languages/", views.LanguageListView.as_view(), name="taxonomy-languages"),
    path("countries/", views.CountryListView.as_view(), name="taxonomy-countries"),
]
