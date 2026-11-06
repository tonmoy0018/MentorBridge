from django.contrib import admin

from .models import CareerGoal, SavedMentor, StudentProfile

admin.site.register(StudentProfile)
admin.site.register(SavedMentor)
admin.site.register(CareerGoal)
