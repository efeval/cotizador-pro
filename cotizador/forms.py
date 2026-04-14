from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Cliente, Producto, Pyme


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _add_bootstrap(form: forms.Form, select_class="form-select"):
    """
    Aplica clases Bootstrap automáticamente a todos los campos.
    """
    for name, field in form.fields.items():
        widget = field.widget

        # checkboxes
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
            continue

        # selects
        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", select_class)
            continue

        # default inputs/textareas
        widget.attrs.setdefault("class", "form-control")


# ------------------------------
#   FORMULARIO DE REGISTRO
# ------------------------------
class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Correo electrónico",
            "autocomplete": "email",
        })
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre de usuario",
                "autocomplete": "username",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilos para passwords
        self.fields["password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Contraseña",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Confirmar contraseña",
            "autocomplete": "new-password",
        })

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email


# ------------------------------
#   FORMULARIO DE PRODUCTO
# ------------------------------
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "nombre",
            "tipo",
            "marca",
            "precio",
            "impuesto",
            "impuesto_adicional",   # ← NUEVO CAMPO EN EL FORM
            "descripcion",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Marca opcional
        self.fields["marca"].required = False

        # Segundo impuesto opcional
        self.fields["impuesto_adicional"].required = False
        self.fields["impuesto"].label = "Impuesto (%)"
        self.fields["impuesto_adicional"].label = "Impuesto adicional (%)"
        self.fields["impuesto_adicional"].help_text = (
            "Opcional. Deja vacío o en 0 si no corresponde."
        )

        # Bootstrap classes
        for name, field in self.fields.items():
            if name == "activo":
                field.widget.attrs["class"] = "form-check-input"
            else:
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (css + " form-control").strip()

# ------------------------------
#   FORMULARIO DE CLIENTE
# ------------------------------
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "email", "telefono", "empresa", "razon_social", "rut"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre completo"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Correo electrónico", "autocomplete": "email"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"}),
            "empresa": forms.TextInput(attrs={"class": "form-control", "placeholder": "Empresa"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control", "placeholder": "Razón social"}),
            "rut": forms.TextInput(attrs={"class": "form-control", "placeholder": "RUT"}),
        }

    def __init__(self, *args, **kwargs):
        # Te llega request.user desde views
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        """
        Tu modelo Cliente NO tiene 'usuario'; tiene 'pyme'.
        Entonces validamos email duplicado dentro de la Pyme del usuario (si existe).
        """
        email = self.cleaned_data["email"]
        qs = Cliente.objects.filter(email__iexact=email)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        # Si viene user, filtramos por pyme asociada al perfil del user (si existe)
        if self.user and hasattr(self.user, "perfil") and self.user.perfil.pyme_id:
            qs = qs.filter(pyme_id=self.user.perfil.pyme_id)

        if qs.exists():
            raise forms.ValidationError("Ya existe un cliente con este email.")
        return email


# ------------------------------
#   FORMULARIO CONFIG PYME
# ------------------------------
class PymeConfigForm(forms.ModelForm):
    class Meta:
        model = Pyme
        fields = [
            "nombre",
            "rut",
            "razon_social",
            "giro",
            "direccion",
            "telefono",
            "email",
            "representante",
            "servicios",
            "descuento_maximo_vendedores",
        ]
        labels = {
            "descuento_maximo_vendedores": "Descuento máximo para vendedores (%)",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
            "rut": forms.TextInput(attrs={"class": "form-control", "placeholder": "RUT"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control", "placeholder": "Razón social"}),
            "giro": forms.TextInput(attrs={"class": "form-control", "placeholder": "Giro"}),
            "direccion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dirección"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
            "representante": forms.TextInput(attrs={"class": "form-control", "placeholder": "Representante"}),
            "servicios": forms.Textarea(attrs={"class": "form-control", "placeholder": "Describe tus servicios / productos", "rows": 4}),
            "descuento_maximo_vendedores": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Ej: 10.00"}),
        }


# ------------------------------
#   FORMULARIO CREAR VENDEDOR 
# ------------------------------
class CrearVendedorForm(UserCreationForm):
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nombre"})
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Apellido"})
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "correo@ejemplo.com", "autocomplete": "email"})
    )
    descuento_maximo_personal = forms.DecimalField(
        label="Descuento máximo personal (%)",
        max_digits=5,
        decimal_places=2,
        required=False,
        help_text="Opcional: límite de descuento sólo para este vendedor.",
        widget=forms.NumberInput(attrs={"placeholder": "Ej: 5.00", "step": "0.01"})
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Nombre de usuario", "autocomplete": "username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Bootstrap a todos
        _add_bootstrap(self)

        # placeholders y atributos para passwords
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Contraseña",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirmar contraseña",
            "autocomplete": "new-password",
        })

        # Email opcional, pero si lo pones, lo validamos con clean_email extra (opcional)
        self.fields["email"].widget.attrs.setdefault("placeholder", "correo@ejemplo.com")


# ------------------------------
#   FORMULARIO ADMIN PYME
# ------------------------------
class PymeAdminForm(forms.ModelForm):
    class Meta:
        model = Pyme
        fields = [
            "nombre",
            "rut",
            "razon_social",
            "giro",
            "direccion",
            "telefono",
            "email",
            "representante",
            "logo",
            "activo",
            "dueno",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
            "rut": forms.TextInput(attrs={"class": "form-control", "placeholder": "RUT"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control", "placeholder": "Razón social"}),
            "giro": forms.TextInput(attrs={"class": "form-control", "placeholder": "Giro"}),
            "direccion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dirección"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
            "representante": forms.TextInput(attrs={"class": "form-control", "placeholder": "Representante"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "dueno": forms.Select(attrs={"class": "form-select"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_bootstrap(self)
        # Ajustes finos
        self.fields["logo"].widget.attrs.update({"class": "form-control"})
        self.fields["dueno"].widget.attrs.update({"class": "form-select"})
        self.fields["activo"].widget.attrs.update({"class": "form-check-input"})
