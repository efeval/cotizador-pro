Cotizador Pro

Sistema web desarrollado con Django para gestionar Pymes, productos, vendedores y cotizaciones de forma centralizada.

Descripción

Cotizador Pro permite administrar una Pyme desde un panel web, gestionar productos, vendedores y generar cotizaciones. El sistema fue configurado localmente con Django, MySQL y XAMPP, y luego preparado para despliegue.

Tecnologías
	•	Python 3.11
	•	Django 4.2
	•	MySQL
	•	XAMPP
	•	Bootstrap 5
	•	Crispy Forms
	•	Pillow
	•	PyMySQL
	•	Gunicorn
	•	WhiteNoise

Instalación local paso a paso

1. Clonar el repositorio
git clone https://github.com/efeval/cotizador-pro.git
cd cotizador-pro

2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

3. Instalar dependencias
pip install -r requirements.txt

4. Configurar base de datos
Este proyecto fue trabajado con MySQL usando XAMPP.
Debes crear una base de datos llamada:
prototipo

5. Configurar settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "prototipo",
        "USER": "root",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": "3306",
    }
}

Dependencias importantes instaladas durante el proceso
pip install django
pip install django-crispy-forms
pip install crispy-bootstrap5
pip install PyMySQL
pip install Pillow
pip install gunicorn whitenoise

Migraciones
python manage.py migrate

Crear superusuario
python manage.py createsuperuser

Ejecutar servidor local
python manage.py runserver

Accesos
	•	Aplicación: http://127.0.0.1:8000/cotizador/
	•	Panel admin: http://127.0.0.1:8000/admin/

Funcionalidades
	•	Gestión de Pymes
	•	Gestión de vendedores
	•	Gestión de productos
	•	Generación de cotizaciones
	•	Panel administrativo
	•	Roles de usuario

Preparación para deploy

Para despliegue se agregaron dependencias como:
	•	Gunicorn
	•	WhiteNoise

Y se dejó el proyecto listo para conectarse a variables de entorno en producción.

Autor

Fernando Valdés
