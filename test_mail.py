import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PROTOTIPO.settings")
django.setup()

from django.core.mail import send_mail

send_mail(
    "Prueba Cotizador",
    "Hola, esto es una prueba",
    os.environ.get("DEFAULT_FROM_EMAIL"),
    ["tu_correo_destino@gmail.com"],
    fail_silently=False,
)
print("OK")
