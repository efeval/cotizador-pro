from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse


# ============================================================
# PYMES Y ROLES
# ============================================================

class Pyme(models.Model):
    """
    Representa a la empresa del COMPRADOR que se registra en el sistema.
    Cada Pyme tiene un dueño (usuario) y uno o más vendedores.
    """
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=20, blank=True)
    razon_social = models.CharField(max_length=200, blank=True)
    giro = models.CharField(max_length=200, blank=True)
    direccion = models.CharField(max_length=250, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="pymes/logos/", blank=True, null=True)

    # NUEVOS CAMPOS
    representante = models.CharField(max_length=200, blank=True)
    servicios = models.TextField(
        blank=True,
        help_text="Descripción de los servicios o productos que ofrece la Pyme.",
    )

    # Dueño de la pyme (comprador) – puede ser opcional
    dueno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pymes_propietario",
        null=True,
        blank=True,
    )

    # Límite de descuento que sus vendedores pueden aplicar (en %)
    descuento_maximo_vendedores = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Porcentaje máximo de descuento permitido a los vendedores.",
    )

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    def logo_url(self):
        try:
            return self.logo.url
        except Exception:
            return ""

    class Meta:
        verbose_name = "Pyme"
        verbose_name_plural = "Pymes"


class PerfilUsuario(models.Model):
    """
    Perfil extra para los usuarios del sistema con roles:
    - SYSTEM_OWNER: Dueño del sistema (normalmente superuser)
    - PYME_OWNER: Dueño de Pyme (comprador)
    - SELLER: Vendedor asociado a una Pyme
    - INVITED: Usuario invitado sin Pyme
    """
    ROLE_CHOICES = [
        ("SYSTEM_OWNER", "Dueño del sistema"),
        ("PYME_OWNER", "Dueño de pyme"),
        ("SELLER", "Vendedor"),
        ("INVITED", "Invitado"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    pyme = models.ForeignKey(
        Pyme,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios",
    )

    descuento_maximo_personal = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Si se define, este límite aplica sólo a este vendedor.",
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def descuento_maximo_permitido(self):
        if self.descuento_maximo_personal is not None:
            return self.descuento_maximo_personal
        if (
            self.role == "SELLER"
            and self.pyme
            and self.pyme.descuento_maximo_vendedores is not None
        ):
            return self.pyme.descuento_maximo_vendedores
        return 0

# ============================================================
# PRODUCTOS
# ============================================================

class Producto(models.Model):
    TIPO_CHOICES = [
        ("software", "Software"),
        ("servicio", "Servicio"),
        ("hardware", "Hardware"),
        ("otros", "Otros"),  # nuevo tipo
    ]

    # Producto asociado a una pyme específica
    pyme = models.ForeignKey(
        Pyme,
        on_delete=models.CASCADE,
        related_name="productos",
        null=True,
        blank=True,
        help_text="Pyme dueña del producto. Si está vacío, se considera genérico.",
    )

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    # Marca opcional
    marca = models.CharField(max_length=100, blank=True)

    precio = models.DecimalField(max_digits=10, decimal_places=2)

    # Impuesto principal (por ejemplo IVA)
    impuesto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("19.0"),
        help_text="Impuesto principal (por ejemplo IVA)."
    )

    # Segundo impuesto OPCIONAL
    impuesto_adicional = models.DecimalField(
        "Segundo impuesto (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Opcional. Úsalo para otro impuesto si aplica. "
            "Para servicios sin impuesto, puedes dejarlo vacío o en 0."
        ),
    )

    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"

    def precio_con_impuesto(self):
        """
        Precio unitario con TODOS los impuestos.
        """
        base = self.precio
        total = base

        # Impuesto principal
        if self.impuesto:
            total += base * (self.impuesto / Decimal("100"))

        # Segundo impuesto opcional
        if self.impuesto_adicional:
            total += base * (self.impuesto_adicional / Decimal("100"))

        return total

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"


# ============================================================
# CLIENTES (clientes de la pyme)
# ============================================================

class Cliente(models.Model):
    """
    Cliente final de una Pyme (a quien se le hace la cotización).
    """
    pyme = models.ForeignKey(
        Pyme,
        on_delete=models.CASCADE,
        related_name="clientes",
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=200)
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    empresa = models.CharField(max_length=200, blank=True)
    razon_social = models.CharField(max_length=200, blank=True)
    rut = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


# ============================================================
# COTIZACIONES
# ============================================================

class Cotizacion(models.Model):
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("enviada", "Enviada"),
        ("aceptada", "Aceptada"),
        ("rechazada", "Rechazada"),
    ]

    pyme = models.ForeignKey(
        Pyme,
        on_delete=models.CASCADE,
        related_name="cotizaciones",
        null=True,
        blank=True,
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)

    # Vendedor autenticado (puede ser null si la hizo un invitado)
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cotizaciones",
    )

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notas = models.TextField(blank=True)

    # Campos para invitado
    creada_por_invitado = models.BooleanField(default=False)
    nombre_invitado = models.CharField(max_length=200, blank=True)
    email_invitado = models.EmailField(blank=True)

    # Extra: ciudad y recomendación del vendedor
    ciudad = models.CharField(max_length=200, blank=True)
    recomendado_por_vendedor = models.BooleanField(default=False)
    vendedor_recomendador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_recomendadas",
    )

    def __str__(self):
        return f"Cotización #{self.id} - {self.cliente.nombre}"

    def calcular_total(self):
        items = self.itemcotizacion_set.all()
        self.total = sum(item.total_con_impuesto() for item in items)
        self.save()
        return self.total

    def get_absolute_url(self):
        return reverse("cotizador:detalle_cotizacion", kwargs={"pk": self.pk})

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"


# ============================================================
# COTIZACIONES - ITEMS
# ============================================================

class ItemCotizacion(models.Model):
    # Usamos string para evitar problemas de orden de definición
    cotizacion = models.ForeignKey("Cotizacion", on_delete=models.CASCADE)
    producto = models.ForeignKey("Producto", on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    # Descuento en %
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Porcentaje de descuento aplicado a este ítem.",
    )

    def subtotal(self):
        """
        Subtotal NETO (sin impuestos), ya con descuento.
        """
        bruto = self.producto.precio * self.cantidad
        if self.descuento_porcentaje:
            bruto = bruto * (Decimal("1") - self.descuento_porcentaje / Decimal("100"))
        return bruto
    def impuesto_principal_valor(self):
        """
        Valor del impuesto principal (por ejemplo IVA) sobre el subtotal neto.
        """
        base = self.subtotal()
        imp = self.producto.impuesto or Decimal("0")
        return base * (imp / Decimal("100"))

    def impuesto_adicional_valor(self):
        """
        Valor del segundo impuesto (opcional) sobre el subtotal neto.
        """
        base = self.subtotal()
        imp2 = self.producto.impuesto_adicional or Decimal("0")
        return base * (imp2 / Decimal("100"))


    def impuesto_valor(self):
        """
        Valor total de impuestos (principal + adicional) sobre el subtotal.
        """
        base = self.subtotal()

        imp_principal = Decimal("0")
        if self.producto.impuesto:
            imp_principal = base * (self.producto.impuesto / Decimal("100"))

        imp_extra = Decimal("0")
        if self.producto.impuesto_adicional:
            imp_extra = base * (self.producto.impuesto_adicional / Decimal("100"))

        return imp_principal + imp_extra

    def total_con_impuesto(self):
        """
        Total FINAL del ítem (subtotal con descuento + TODOS los impuestos).
        """
        return self.subtotal() + self.impuesto_valor()

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"
