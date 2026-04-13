from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import (
    CrearVendedorForm,
    ClienteForm,
    ProductoForm,
    PymeAdminForm,
    PymeConfigForm,
    RegistroUsuarioForm,
)
from .models import (
    Cliente,
    Cotizacion,
    ItemCotizacion,
    PerfilUsuario,
    Producto,
    Pyme,
)

User = get_user_model()

# ============================================================
#  HELPERS / ROLES / PYME ACTIVA (SESION)
# ============================================================

def obtener_perfil(user):
    try:
        return user.perfil
    except PerfilUsuario.DoesNotExist:
        return None


def es_system_owner(user):
    if user.is_superuser:
        return True
    perfil = obtener_perfil(user)
    return bool(perfil and perfil.role == "SYSTEM_OWNER")


def obtener_pyme_activa(request):
    pyme_id = request.session.get("pyme_id")
    if not pyme_id:
        return None
    try:
        return Pyme.objects.get(pk=pyme_id, activo=True)
    except Pyme.DoesNotExist:
        return None


def obtener_pyme_usuario(user, request=None):
    """
    - PYME_OWNER: prioriza pyme en sesión (si existe y es suya), si no usa perfil.pyme
    - SELLER: usa perfil.pyme
    - SYSTEM_OWNER / INVITED: None
    """
    perfil = obtener_perfil(user)
    if not perfil:
        return None

    if perfil.role == "PYME_OWNER":
        if request:
            pyme_sesion = obtener_pyme_activa(request)
            if pyme_sesion and pyme_sesion.dueno_id == user.id:
                return pyme_sesion
        return perfil.pyme

    if perfil.role == "SELLER":
        return perfil.pyme

    return None


def bloquear_system_owner(mensaje):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if es_system_owner(request.user):
                messages.error(request, mensaje)
                return redirect("cotizador:dashboard")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def requiere_roles(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            perfil = obtener_perfil(request.user)
            if not perfil:
                messages.error(request, "Tu usuario no tiene perfil configurado.")
                return redirect("cotizador:dashboard")
            if perfil.role not in roles:
                messages.error(request, "No tienes permisos para acceder a esta sección.")
                return redirect("cotizador:dashboard")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ============================================================
#  PUBLIC (INVITADOS) - MARKETPLACE
# ============================================================

def home_publica(request):
    """
    Marketplace público:
    - Invitados (no logueados) y usuarios INVITED (logueados) ven catálogo.
    - PYME_OWNER / SELLER -> dashboard
    """
    if request.user.is_authenticated and not es_system_owner(request.user):
        perfil = obtener_perfil(request.user)
        if perfil and perfil.role in ("PYME_OWNER", "SELLER"):
            return redirect("cotizador:dashboard")

    q = request.GET.get("q", "").strip()
    pymes = Pyme.objects.filter(activo=True)

    if q:
        pymes = pymes.filter(
            models.Q(nombre__icontains=q)
            | models.Q(razon_social__icontains=q)
            | models.Q(giro__icontains=q)
        )

    pymes = pymes.order_by("nombre")
    return render(request, "cotizador/public_home.html", {"pymes": pymes, "q": q})


def pyme_publica(request, pyme_id):
    pyme = get_object_or_404(Pyme, pk=pyme_id, activo=True)
    productos = Producto.objects.filter(pyme=pyme, activo=True).order_by("nombre")
    return render(request, "cotizador/public_pyme.html", {"pyme": pyme, "productos": productos})


# ============================================================
#  REGISTRO / LOGIN
# ============================================================

def registrar_usuario(request):
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save()

            PerfilUsuario.objects.create(
                user=usuario,
                role="INVITED",   # queda como invitado
                pyme=None,
            )

            username = form.cleaned_data["username"]
            password = form.cleaned_data["password1"]
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Cuenta creada correctamente.")
                return redirect("cotizador:home_publica")


            messages.error(request, "Error al iniciar sesión automáticamente.")
            return redirect("cotizador:login")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = RegistroUsuarioForm()

    return render(request, "cotizador/registrar.html", {"form": form})


def login_view(request):
    """
    - SYSTEM_OWNER -> dashboard
    - PYME_OWNER:
        * 0 pymes -> configurar_pyme
        * 1 pyme -> fija sesión y perfil.pyme y dashboard
        * >1 -> seleccionar_pyme
    - SELLER -> dashboard
    - INVITED -> dashboard
    """
    error = None

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if es_system_owner(user):
                return redirect("cotizador:dashboard")

            perfil = obtener_perfil(user)
            if not perfil:
                return redirect("cotizador:dashboard")

            if perfil.role == "PYME_OWNER":
                pymes_dueno = Pyme.objects.filter(dueno=user, activo=True)

                if not pymes_dueno.exists():
                    return redirect("cotizador:configurar_pyme")

                if pymes_dueno.count() == 1:
                    unica = pymes_dueno.first()
                    request.session["pyme_id"] = unica.id
                    if perfil.pyme_id != unica.id:
                        perfil.pyme = unica
                        perfil.save()
                    return redirect("cotizador:dashboard")

                return redirect("cotizador:seleccionar_pyme")

            return redirect("cotizador:dashboard")

        error = "Usuario o contraseña incorrectos."

    return render(request, "cotizador/index.html", {"error": error})


# ============================================================
#  DASHBOARD
# ============================================================

@login_required
def dashboard(request):
    user = request.user

    # ===== SYSTEM OWNER =====
    if es_system_owner(user):
        stats = {
            "total_pymes": Pyme.objects.count(),
            "pymes_activas": Pyme.objects.filter(activo=True).count(),
            "pymes_inactivas": Pyme.objects.filter(activo=False).count(),
            "total_usuarios": PerfilUsuario.objects.count(),
        }
        pymes = Pyme.objects.all().order_by("nombre")
        return render(
            request,
            "cotizador/dashboard.html",
            {"stats": stats, "pymes": pymes, "es_system_owner": True},
        )

    perfil = obtener_perfil(user)
    if not perfil:
        messages.error(request, "Tu usuario no tiene perfil configurado.")
        return redirect("cotizador:login")
    
@login_required
def dashboard(request):
    user = request.user

    # ===== SYSTEM OWNER =====
    if es_system_owner(user):
        stats = {
            "total_pymes": Pyme.objects.count(),
            "pymes_activas": Pyme.objects.filter(activo=True).count(),
            "pymes_inactivas": Pyme.objects.filter(activo=False).count(),
            "total_usuarios": PerfilUsuario.objects.count(),
        }
        pymes = Pyme.objects.all().order_by("nombre")
        return render(
            request,
            "cotizador/dashboard.html",
            {"stats": stats, "pymes": pymes, "es_system_owner": True},
        )

    perfil = obtener_perfil(user)
    if not perfil:
        messages.error(request, "Tu usuario no tiene perfil configurado.")
        return redirect("cotizador:login")

    # ✅ INVITED: NO tiene dashboard, va al marketplace (pymes públicas)
    if perfil.role == "INVITED":
        messages.info(
            request,
            "Aún no tienes una Pyme para gestionar. Puedes cotizar en las Pymes disponibles abajo. "
            "Si quieres crear tu propia Pyme y usar Cotizador PRO, contáctanos: "
            "Cotizadorpro@gmail.com / +56956128195"
        )
        return redirect("cotizador:home_publica")

    # ===== PYME_OWNER multi-pyme =====
    if perfil.role == "PYME_OWNER":
        pymes_dueno = Pyme.objects.filter(dueno=user, activo=True)
        pyme_sesion = obtener_pyme_activa(request)

        if pymes_dueno.count() > 1 and not pyme_sesion:
            return redirect("cotizador:seleccionar_pyme")

        if pymes_dueno.count() == 1 and not pyme_sesion:
            unica = pymes_dueno.first()
            request.session["pyme_id"] = unica.id
            if perfil.pyme_id != unica.id:
                perfil.pyme = unica
                perfil.save()

    pyme = obtener_pyme_usuario(user, request=request)

    if not pyme:
        messages.warning(request, "Tu usuario aún no tiene una Pyme activa.")
        stats = {"total_productos": 0, "total_clientes": 0}
    else:
        stats = {
            "total_productos": Producto.objects.filter(pyme=pyme, activo=True).count(),
            "total_clientes": Cliente.objects.filter(pyme=pyme).count(),
        }

    return render(
        request,
        "cotizador/dashboard.html",
        {"stats": stats, "es_system_owner": False, "pyme": pyme},
    )


    # ===== PYME_OWNER multi-pyme: si no eligió, lo mando a seleccionar =====
    if perfil.role == "PYME_OWNER":
        pymes_dueno = Pyme.objects.filter(dueno=user, activo=True)
        pyme_sesion = obtener_pyme_activa(request)

        if pymes_dueno.count() > 1 and not pyme_sesion:
            return redirect("cotizador:seleccionar_pyme")

        if pymes_dueno.count() == 1 and not pyme_sesion:
            unica = pymes_dueno.first()
            request.session["pyme_id"] = unica.id
            if perfil.pyme_id != unica.id:
                perfil.pyme = unica
                perfil.save()

    pyme = obtener_pyme_usuario(user, request=request)

    if not pyme:
        stats = {"total_productos": 0, "total_clientes": 0}
    else:
        stats = {
            "total_productos": Producto.objects.filter(pyme=pyme, activo=True).count(),
            "total_clientes": Cliente.objects.filter(pyme=pyme).count(),
        }

    return render(
        request,
        "cotizador/dashboard.html",
        {"stats": stats, "es_system_owner": False, "pyme": pyme},
    )


# ============================================================
#  CLIENTES  (REGLA: SELLER NO PUEDE)
# ============================================================

@login_required
@bloquear_system_owner("El dueño del sistema no puede gestionar clientes.")
@requiere_roles("PYME_OWNER")
def lista_clientes(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    clientes = Cliente.objects.filter(pyme=pyme) if pyme else Cliente.objects.none()

    query = request.GET.get("q", "").strip()
    if query:
        clientes = clientes.filter(
            models.Q(nombre__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(empresa__icontains=query)
        )

    clientes = clientes.order_by("-fecha_creacion")
    return render(request, "cotizador/clientes.html", {"clientes": clientes, "q": query})


@login_required
@bloquear_system_owner("El dueño del sistema no puede crear clientes.")
@requiere_roles("PYME_OWNER")
def crear_cliente(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.error(request, "No tienes una Pyme activa.")
        return redirect("cotizador:dashboard")

    if request.method == "POST":
        form = ClienteForm(request.POST, user=request.user)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.pyme = pyme
            cliente.save()
            messages.success(request, "Cliente creado exitosamente.")
            return redirect("cotizador:lista_clientes")
    else:
        form = ClienteForm(user=request.user)

    return render(request, "cotizador/cliente_form.html", {"form": form, "accion": "Nuevo"})


@login_required
@bloquear_system_owner("El dueño del sistema no puede editar clientes.")
@requiere_roles("PYME_OWNER")
def editar_cliente(request, pk):
    pyme = obtener_pyme_usuario(request.user, request=request)
    cliente = get_object_or_404(Cliente, pk=pk, pyme=pyme)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("cotizador:lista_clientes")
    else:
        form = ClienteForm(instance=cliente, user=request.user)

    return render(request, "cotizador/cliente_form.html", {"form": form, "accion": "Editar"})


@login_required
@bloquear_system_owner("El dueño del sistema no puede eliminar clientes.")
@requiere_roles("PYME_OWNER")
def eliminar_cliente(request, pk):
    pyme = obtener_pyme_usuario(request.user, request=request)
    cliente = get_object_or_404(Cliente, pk=pk, pyme=pyme)

    if request.method == "POST":
        cliente.delete()
        messages.success(request, "Cliente eliminado correctamente.")
        return redirect("cotizador:lista_clientes")

    return render(request, "cotizador/cliente_confirmar_eliminar.html", {"cliente": cliente})


# ============================================================
#  PRODUCTOS (solo PYME_OWNER)
# ============================================================

@login_required
@bloquear_system_owner("El dueño del sistema no gestiona productos.")
@requiere_roles("PYME_OWNER")
def lista_productos(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    productos = Producto.objects.filter(pyme=pyme) if pyme else Producto.objects.none()

    query = request.GET.get("q", "").strip()
    if query:
        productos = productos.filter(
            models.Q(nombre__icontains=query)
            | models.Q(marca__icontains=query)
            | models.Q(tipo__icontains=query)
        )

    productos = productos.order_by("-fecha_creacion")
    return render(request, "cotizador/productos.html", {"productos": productos, "q": query})


@login_required
@bloquear_system_owner("El dueño del sistema no puede crear productos.")
@requiere_roles("PYME_OWNER")
def crear_producto(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.error(request, "No tienes una Pyme activa.")
        return redirect("cotizador:dashboard")

    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.pyme = pyme
            producto.save()
            messages.success(request, "Producto creado exitosamente.")
            return redirect("cotizador:lista_productos")
    else:
        form = ProductoForm()

    return render(request, "cotizador/producto_form.html", {"form": form, "accion": "Nuevo"})


@login_required
@bloquear_system_owner("El dueño del sistema no puede editar productos.")
@requiere_roles("PYME_OWNER")
def editar_producto(request, pk):
    pyme = obtener_pyme_usuario(request.user, request=request)
    producto = get_object_or_404(Producto, pk=pk, pyme=pyme)

    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("cotizador:lista_productos")
    else:
        form = ProductoForm(instance=producto)

    return render(request, "cotizador/producto_form.html", {"form": form, "accion": "Editar"})


@login_required
@bloquear_system_owner("El dueño del sistema no puede eliminar productos.")
@requiere_roles("PYME_OWNER")
def eliminar_producto(request, pk):
    pyme = obtener_pyme_usuario(request.user, request=request)
    producto = get_object_or_404(Producto, pk=pk, pyme=pyme)

    if request.method == "POST":
        producto.delete()
        messages.success(request, "Producto eliminado correctamente.")
        return redirect("cotizador:lista_productos")

    return render(request, "cotizador/producto_confirmar_eliminar.html", {"producto": producto})


# ============================================================
#  COTIZACIONES (SELLER)
# ============================================================

@login_required
@bloquear_system_owner("El dueño del sistema no puede ver cotizaciones.")
@requiere_roles("SELLER")
def lista_cotizaciones(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    cotizaciones = (
        Cotizacion.objects.filter(pyme=pyme).order_by("-fecha_creacion")
        if pyme else Cotizacion.objects.none()
    )
    return render(request, "cotizador/cotizaciones.html", {"cotizaciones": cotizaciones})


@login_required
@bloquear_system_owner("El dueño del sistema no puede crear cotizaciones.")
@requiere_roles("SELLER")
def nueva_cotizacion(request):
    user = request.user
    pyme = obtener_pyme_usuario(user, request=request)
    if not pyme:
        messages.error(request, "No tienes una Pyme asociada para crear cotizaciones.")
        return redirect("cotizador:dashboard")

    productos = Producto.objects.filter(pyme=pyme, activo=True)
    clientes = Cliente.objects.filter(pyme=pyme)

    try:
        descuento_maximo = user.perfil.descuento_maximo_permitido()
    except Exception:
        descuento_maximo = 0

    if request.method == "POST":
        cliente_id = request.POST.get("cliente")
        cliente = get_object_or_404(Cliente, id=cliente_id, pyme=pyme)

        cotizacion = Cotizacion.objects.create(
            pyme=pyme,
            cliente=cliente,
            vendedor=user,
            estado="borrador",
            creada_por_invitado=False,
        )

        productos_ids = request.POST.getlist("producto")
        cantidades = request.POST.getlist("cantidad")
        descuentos = request.POST.getlist("descuento", [])

        if not descuentos or len(descuentos) != len(productos_ids):
            descuentos = ["0"] * len(productos_ids)

        for prod_id, cantidad, desc in zip(productos_ids, cantidades, descuentos):
            if not prod_id or not cantidad:
                continue

            producto = get_object_or_404(Producto, id=prod_id, pyme=pyme)

            try:
                cantidad_int = int(cantidad)
                if cantidad_int <= 0:
                    continue
            except ValueError:
                continue

            try:
                desc_float = float(desc.replace(",", ".")) if desc else 0.0
            except ValueError:
                desc_float = 0.0

            if desc_float > float(descuento_maximo):
                desc_float = float(descuento_maximo)

            ItemCotizacion.objects.create(
                cotizacion=cotizacion,
                producto=producto,
                cantidad=cantidad_int,
                descuento_porcentaje=desc_float,
            )

        cotizacion.calcular_total()
        return redirect("cotizador:lista_cotizaciones")

    return render(
        request,
        "cotizador/nueva_cotizacion.html",
        {"productos": productos, "clientes": clientes, "descuento_maximo": descuento_maximo},
    )


@login_required
@bloquear_system_owner("El dueño del sistema no puede ver cotizaciones.")
@requiere_roles("SELLER")
def detalle_cotizacion(request, pk):
    pyme = obtener_pyme_usuario(request.user, request=request)
    cotizacion = get_object_or_404(Cotizacion, pk=pk, pyme=pyme)
    items = cotizacion.itemcotizacion_set.select_related("producto").all()

    subtotal_general = sum(it.subtotal() for it in items)
    impuestos_totales = sum(it.impuesto_valor() for it in items)
    total_con_impuestos = subtotal_general + impuestos_totales

    return render(
        request,
        "cotizador/detalle_cotizacion.html",
        {
            "cotizacion": cotizacion,
            "items": items,
            "subtotal_general": subtotal_general,
            "impuestos_totales": impuestos_totales,
            "total_con_impuestos": total_con_impuestos,
        },
    )


@login_required
@require_POST
@bloquear_system_owner("El dueño del sistema no puede enviar cotizaciones.")
@requiere_roles("SELLER")
def enviar_cotizacion(request, pk):
    """
    Botón para vendedor: enviar cotización por correo
    (con BCC al dueño/admin de la Pyme siempre).
    """
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.error(request, "No tienes una Pyme asociada.")
        return redirect("cotizador:dashboard")

    cotizacion = get_object_or_404(Cotizacion, pk=pk, pyme=pyme)
    items = cotizacion.itemcotizacion_set.select_related("producto").all()

    to_email = (cotizacion.cliente.email or "").strip()
    if not to_email:
        messages.error(request, "La cotización no tiene email de cliente.")
        return redirect("cotizador:detalle_cotizacion", pk=cotizacion.pk)

    subtotal_general = sum(it.subtotal() for it in items)
    impuestos_totales = sum(it.impuesto_valor() for it in items)
    total_con_impuestos = subtotal_general + impuestos_totales

    bcc_list = []
    if pyme.dueno and (pyme.dueno.email or "").strip():
        bcc_list.append(pyme.dueno.email.strip())

    url_detalle = request.build_absolute_uri(
        reverse("cotizador:detalle_cotizacion", args=[cotizacion.pk])
    )

    context = {
        "cotizacion": cotizacion,
        "pyme": pyme,
        "cliente": cotizacion.cliente,
        "items": items,
        "url_detalle": url_detalle,
        "subtotal_general": subtotal_general,
        "impuestos_totales": impuestos_totales,
        "total_con_impuestos": total_con_impuestos,
    }

    try:
        subject = f"Cotización #{cotizacion.id} - {pyme.nombre}"
        html_content = render_to_string("cotizador/emails/cotizacion.html", context)
        text_content = strip_tags(html_content)

        timeout = getattr(settings, "EMAIL_TIMEOUT", 10)
        connection = get_connection(timeout=timeout)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            bcc=bcc_list,
            connection=connection,
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        messages.success(request, "Cotización enviada por correo.")
    except Exception as e:
        messages.error(request, f"No se pudo enviar el correo: {e}")

    return redirect("cotizador:detalle_cotizacion", pk=cotizacion.pk)


# ============================================================
#  COTIZACIÓN COMO INVITADO (PUBLICA)
# ============================================================

@csrf_exempt
def nueva_cotizacion_invitado(request, pyme_id):
    pyme = get_object_or_404(Pyme, pk=pyme_id, activo=True)
    productos = Producto.objects.filter(pyme=pyme, activo=True)
    vendedores = (
        PerfilUsuario.objects
        .filter(pyme=pyme, role="SELLER")
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__username")
    )

    if request.method == "POST":
        nombre_invitado = request.POST.get("nombre_invitado", "").strip()
        email_invitado = request.POST.get("email_invitado", "").strip()
        ciudad = request.POST.get("ciudad", "").strip()

        recomendado = request.POST.get("recomendado_por_vendedor") == "si"
        vendedor_id = request.POST.get("vendedor_recomendador") if recomendado else None

        vendedor_obj = None
        if vendedor_id:
            vendedor_obj = get_object_or_404(User, pk=vendedor_id)

        nombre_cliente = (request.POST.get("nombre_cliente", nombre_invitado).strip() or "Cliente invitado")
        email_cliente = (request.POST.get("email_cliente", email_invitado).strip() or email_invitado)

        # Cliente asociado a la Pyme (REGLA)
        cliente = Cliente.objects.create(
            pyme=pyme,
            nombre=nombre_cliente,
            email=email_cliente,
        )

        cotizacion = Cotizacion.objects.create(
            pyme=pyme,
            cliente=cliente,
            vendedor=None,
            estado="borrador",
            creada_por_invitado=True,
            nombre_invitado=nombre_invitado,
            email_invitado=email_invitado,
            ciudad=ciudad,
            recomendado_por_vendedor=recomendado,
            vendedor_recomendador=vendedor_obj,
        )

        productos_ids = request.POST.getlist("producto")
        cantidades = request.POST.getlist("cantidad")

        for prod_id, cantidad in zip(productos_ids, cantidades):
            if not prod_id or not cantidad:
                continue

            producto = get_object_or_404(Producto, id=prod_id, pyme=pyme)

            try:
                cantidad_int = int(cantidad)
                if cantidad_int <= 0:
                    continue
            except ValueError:
                continue

            ItemCotizacion.objects.create(
                cotizacion=cotizacion,
                producto=producto,
                cantidad=cantidad_int,
                descuento_porcentaje=0,
            )

        cotizacion.calcular_total()

        items = cotizacion.itemcotizacion_set.select_related("producto").all()

        subtotal_general = sum(it.subtotal() for it in items)
        impuestos_totales = sum(it.impuesto_valor() for it in items)
        total_con_impuestos = subtotal_general + impuestos_totales

        to_email = (cliente.email or email_invitado or "").strip()

        cc_list = []
        if pyme.dueno and (pyme.dueno.email or "").strip():
            cc_list.append(pyme.dueno.email.strip())

        if to_email:
            try:
                subject = f"Cotización #{cotizacion.id} - {pyme.nombre}"
                url_detalle = request.build_absolute_uri(
                    reverse("cotizador:detalle_cotizacion_publica", args=[cotizacion.pk])
                )

                context = {
                    "cotizacion": cotizacion,
                    "pyme": pyme,
                    "cliente": cliente,
                    "items": items,
                    "url_detalle": url_detalle,
                    "subtotal_general": subtotal_general,
                    "impuestos_totales": impuestos_totales,
                    "total_con_impuestos": total_con_impuestos,
                }

                html_content = render_to_string("cotizador/emails/cotizacion.html", context)
                text_content = strip_tags(html_content)

                timeout = getattr(settings, "EMAIL_TIMEOUT", 10)
                connection = get_connection(timeout=timeout)

                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[to_email],
                    cc=cc_list,
                    connection=connection,
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
            except Exception as e:
                messages.error(request, f"No se pudo enviar el correo: {e}")

        return redirect("cotizador:detalle_cotizacion_publica", pk=cotizacion.pk)

    return render(
        request,
        "cotizador/nueva_cotizacion_invitados.html",
        {"pyme": pyme, "productos": productos, "vendedores": vendedores},
    )


def detalle_cotizacion_publica(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk, creada_por_invitado=True)
    items = cotizacion.itemcotizacion_set.select_related("producto").all()

    subtotal_general = sum(it.subtotal() for it in items)
    impuestos_totales = sum(it.impuesto_valor() for it in items)
    total_con_impuestos = subtotal_general + impuestos_totales

    return render(
        request,
        "cotizador/detalle_cotizacion_publica.html",
        {
            "cotizacion": cotizacion,
            "items": items,
            "subtotal_general": subtotal_general,
            "impuestos_totales": impuestos_totales,
            "total_con_impuestos": total_con_impuestos,
        },
    )


# ============================================================
#  MI PYME (PYME_OWNER)
# ============================================================

@login_required
@requiere_roles("PYME_OWNER")
def mi_pyme_detalle(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.warning(request, "Aún no tienes una Pyme. Completa el formulario para crearla.")
        return redirect("cotizador:configurar_pyme")
    return render(request, "cotizador/mi_pyme_detalle.html", {"pyme": pyme})


@login_required
@requiere_roles("PYME_OWNER")
def configurar_pyme(request):
    user = request.user
    pyme = obtener_pyme_usuario(user, request=request)

    if not pyme:
        pyme = Pyme(dueno=user)

    if request.method == "POST":
        form = PymeConfigForm(request.POST, request.FILES, instance=pyme)
        if form.is_valid():
            pyme = form.save(commit=False)
            pyme.dueno = user
            pyme.activo = True
            pyme.save()

            perfil = user.perfil
            perfil.pyme = pyme
            perfil.save()

            request.session["pyme_id"] = pyme.id

            messages.success(request, "Datos de la Pyme actualizados correctamente.")
            return redirect("cotizador:mi_pyme_detalle")
    else:
        form = PymeConfigForm(instance=pyme)

    return render(request, "cotizador/pyme_configurar.html", {"form": form, "pyme": pyme})


@login_required
@requiere_roles("PYME_OWNER")
def seleccionar_pyme(request):
    user = request.user
    perfil = user.perfil

    pymes_dueno = Pyme.objects.filter(dueno=user, activo=True).order_by("nombre")

    if not pymes_dueno.exists():
        messages.warning(request, "Aún no tienes Pymes asociadas.")
        return redirect("cotizador:configurar_pyme")

    if pymes_dueno.count() == 1:
        unica = pymes_dueno.first()
        request.session["pyme_id"] = unica.id
        perfil.pyme = unica
        perfil.save()
        return redirect("cotizador:dashboard")

    if request.method == "POST":
        pyme_id = request.POST.get("pyme_id")
        pyme = get_object_or_404(Pyme, pk=pyme_id, dueno=user, activo=True)

        request.session["pyme_id"] = pyme.id
        perfil.pyme = pyme
        perfil.save()

        messages.success(request, f"Ahora estás gestionando: {pyme.nombre}")
        return redirect("cotizador:dashboard")

    pyme_actual = obtener_pyme_activa(request) or perfil.pyme

    return render(
        request,
        "cotizador/seleccionar_pyme.html",
        {"pymes": pymes_dueno, "pyme_actual": pyme_actual},
    )


# ============================================================
#  ADMIN PYMES (SYSTEM_OWNER)
# ============================================================

@login_required
def admin_lista_pymes(request):
    if not es_system_owner(request.user):
        messages.error(request, "Sólo el dueño del sistema puede ver todas las Pymes.")
        return redirect("cotizador:dashboard")

    pymes = Pyme.objects.all().order_by("nombre")
    return render(request, "cotizador/admin_pymes_lista.html", {"pymes": pymes})


@login_required
def admin_crear_pyme(request):
    if not es_system_owner(request.user):
        messages.error(request, "Sólo el dueño del sistema puede crear Pymes.")
        return redirect("cotizador:dashboard")

    if request.method == "POST":
        form = PymeAdminForm(request.POST, request.FILES)
        if form.is_valid():
            pyme = form.save()

            dueno = pyme.dueno
            if dueno:
                perfil, created = PerfilUsuario.objects.get_or_create(
                    user=dueno,
                    defaults={"role": "PYME_OWNER", "pyme": pyme},
                )
                if not created:
                    if perfil.role != "SYSTEM_OWNER":
                        perfil.role = "PYME_OWNER"
                    perfil.pyme = pyme
                    perfil.save()

            messages.success(request, "Pyme creada correctamente.")
            return redirect("cotizador:admin_lista_pymes")
    else:
        form = PymeAdminForm()

    return render(request, "cotizador/admin_pyme_form.html", {"form": form, "titulo": "Nueva Pyme"})


@login_required
def admin_editar_pyme(request, pk):
    if not es_system_owner(request.user):
        messages.error(request, "Sólo el dueño del sistema puede editar Pymes.")
        return redirect("cotizador:dashboard")

    pyme = get_object_or_404(Pyme, pk=pk)

    if request.method == "POST":
        form = PymeAdminForm(request.POST, request.FILES, instance=pyme)
        if form.is_valid():
            pyme = form.save()

            dueno = pyme.dueno
            if dueno:
                perfil, created = PerfilUsuario.objects.get_or_create(
                    user=dueno,
                    defaults={"role": "PYME_OWNER", "pyme": pyme},
                )
                if not created:
                    if perfil.role != "SYSTEM_OWNER":
                        perfil.role = "PYME_OWNER"
                    perfil.pyme = pyme
                    perfil.save()

            messages.success(request, "Pyme actualizada correctamente.")
            return redirect("cotizador:admin_lista_pymes")
    else:
        form = PymeAdminForm(instance=pyme)

    return render(
        request,
        "cotizador/admin_pyme_form.html",
        {"form": form, "titulo": f"Editar Pyme: {pyme.nombre}"},
    )


@login_required
def admin_eliminar_pyme(request, pk):
    if not es_system_owner(request.user):
        messages.error(request, "Sólo el dueño del sistema puede eliminar Pymes.")
        return redirect("cotizador:dashboard")

    pyme = get_object_or_404(Pyme, pk=pk)

    if request.method == "POST":
        nombre = pyme.nombre
        pyme.delete()
        messages.success(request, f"La Pyme «{nombre}» fue eliminada correctamente.")
        return redirect("cotizador:admin_lista_pymes")

    return render(request, "cotizador/admin_pyme_confirmar_eliminar.html", {"pyme": pyme})


# ============================================================
#  VENDEDORES (PYME_OWNER)
# ============================================================

@login_required
@requiere_roles("PYME_OWNER")
def lista_vendedores(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.warning(request, "Primero configura tu Pyme.")
        return redirect("cotizador:configurar_pyme")

    vendedores = PerfilUsuario.objects.filter(pyme=pyme, role="SELLER").select_related("user")
    return render(request, "cotizador/vendedores_lista.html", {"pyme": pyme, "vendedores": vendedores})


@login_required
@requiere_roles("PYME_OWNER")
def crear_vendedor(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    if not pyme:
        messages.warning(request, "Primero configura tu Pyme.")
        return redirect("cotizador:configurar_pyme")

    if request.method == "POST":
        form = CrearVendedorForm(request.POST)
        if form.is_valid():
            nuevo_usuario = form.save()
            PerfilUsuario.objects.create(
                user=nuevo_usuario,
                role="SELLER",
                pyme=pyme,
                descuento_maximo_personal=form.cleaned_data.get("descuento_maximo_personal"),
            )
            messages.success(request, "Vendedor creado correctamente.")
            return redirect("cotizador:lista_vendedores")
    else:
        form = CrearVendedorForm()

    return render(request, "cotizador/vendedor_form.html", {"form": form, "pyme": pyme})


# ============================================================
#  API PRODUCTOS (solo PYME_OWNER)
# ============================================================

@login_required
@csrf_exempt
@bloquear_system_owner("El dueño del sistema no usa la API de productos.")
@requiere_roles("PYME_OWNER")
def api_productos(request):
    pyme = obtener_pyme_usuario(request.user, request=request)
    productos_qs = Producto.objects.filter(pyme=pyme, activo=True) if pyme else Producto.objects.none()
    productos = list(productos_qs.values("id", "nombre", "precio", "impuesto", "impuesto_adicional", "tipo"))
    return JsonResponse(productos, safe=False)
