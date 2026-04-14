# cotizador/context_processors.py
from .models import PerfilUsuario, Pyme

def user_context(request):
    perfil = None
    es_system_owner_flag = False
    pyme_actual = None
    puede_elegir_pyme = False

    if request.user.is_authenticated:
        # Perfil
        try:
            perfil = request.user.perfil
        except PerfilUsuario.DoesNotExist:
            perfil = None

        # Dueño del sistema
        if request.user.is_superuser or (perfil and perfil.role == "SYSTEM_OWNER"):
            es_system_owner_flag = True

        # Pyme actualmente seleccionada (id guardado en sesión)
        pyme_id = request.session.get("pyme_actual_id")
        if pyme_id:
            pyme_actual = Pyme.objects.filter(id=pyme_id).first()

        # ¿Puede elegir Pyme? (tiene más de una asociada como dueño)
        if perfil and perfil.role == "PYME_OWNER":
            pymes_dueno = Pyme.objects.filter(dueno=request.user)
            puede_elegir_pyme = pymes_dueno.count() > 1

    return {
        "perfil": perfil,
        "es_system_owner_flag": es_system_owner_flag,
        "pyme_actual": pyme_actual,
        "puede_elegir_pyme": puede_elegir_pyme,
    }
