import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PROTOTIPO.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123")

if not User.objects.filter(username=username).exists():
    print("Creando superusuario...")
    User.objects.create_superuser(username, email, password)
else:
    print("El superusuario ya existe.")