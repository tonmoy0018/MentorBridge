from rest_framework.permissions import BasePermission

from apps.users.models import Role


class _RolePermission(BasePermission):
    role: str = ""
    message = "Your account type can't do that."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.role == self.role)


class IsStudent(_RolePermission):
    role = Role.STUDENT
    message = "Only student accounts can do that."


class IsMentor(_RolePermission):
    role = Role.MENTOR
    message = "Only mentor accounts can do that."


class IsAdminRole(_RolePermission):
    """MentorBridge administrators: admin role AND staff flag (both set by createsuperuser)."""

    role = Role.ADMIN
    message = "Only administrators can do that."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_staff


class IsStudentOrMentor(BasePermission):
    message = "Only student and mentor accounts can do that."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and user.role in (Role.STUDENT, Role.MENTOR)
        )
