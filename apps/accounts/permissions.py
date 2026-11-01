"""Server-side role enforcement. The UI only hides links; these classes decide."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR, has_role


class _RolePermission(BasePermission):
    roles: tuple[str, ...] = ()
    message = "Your role is not allowed to perform this action."

    def has_permission(self, request, view) -> bool:
        return has_role(request.user, *self.roles)


class IsAdministrator(_RolePermission):
    roles = (ROLE_ADMIN,)


class IsEngineer(_RolePermission):
    roles = (ROLE_ENGINEER,)


class IsSupervisor(_RolePermission):
    roles = (ROLE_SUPERVISOR,)


class IsSupervisorOrAdmin(_RolePermission):
    roles = (ROLE_SUPERVISOR, ROLE_ADMIN)


class IsEngineerOrAdministrator(_RolePermission):
    roles = (ROLE_ENGINEER, ROLE_ADMIN)
