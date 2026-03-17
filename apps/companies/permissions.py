from rest_framework.permissions import BasePermission


class IsOrganizationOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        organization = getattr(obj, "organization", obj)
        return request.user.is_superuser or organization.owner_id == request.user.id
