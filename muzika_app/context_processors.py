from .models import Group, Membership


def nav_group(request):
    """Pateikia navigacijai paskutinę aplankytą grupę, kad „Žaidimai"/„Statistika"
    nuorodos neišnyktų naršant per bendrus (ne grupės) puslapius.

    Grąžina `nav_group` – grupės objektą arba None.
    """
    if not request.user.is_authenticated:
        return {}

    group = None

    # 1) Pirmenybė – paskutinė sesijoje išsaugota grupė
    code = request.session.get('last_visited_group_code')
    if code:
        group = Group.objects.filter(code=code).first()
        # Įsitikinam, kad vartotojas vis dar narys (arba superuser)
        if group and not request.user.is_superuser:
            is_member = Membership.objects.filter(group=group, user=request.user).exists()
            if not is_member:
                group = None

    # 2) Jei nėra – imam bet kurią vartotojo grupę
    if group is None:
        membership = (
            Membership.objects
            .filter(user=request.user)
            .select_related('group')
            .order_by('-id')
            .first()
        )
        if membership:
            group = membership.group

    return {'nav_group': group}
