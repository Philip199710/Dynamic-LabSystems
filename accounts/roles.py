"""Who counts as a Dynamic APAC admin ("us") versus lab staff."""

DYNAMIC_ADMIN_GROUP = "Dynamic Admin"


def is_dynamic_admin(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=DYNAMIC_ADMIN_GROUP).exists()
