"""Role names are Django Group names, so authorization data lives in the DB."""

ROLE_ADMIN = "Administrator"
ROLE_ENGINEER = "Engineer"
ROLE_SUPERVISOR = "Supervisor"
ALL_ROLES = (ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR)


def role_of(user) -> str | None:
    """Return the user's single role, or None. A superuser counts as Administrator."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    names = set(user.groups.values_list("name", flat=True))
    for role in ALL_ROLES:
        if role in names:
            return role
    return ROLE_ADMIN if user.is_superuser else None


def has_role(user, *roles: str) -> bool:
    return role_of(user) in roles
