from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "cotizador"

urlpatterns = [
    # Público
    path("", views.home_publica, name="home_publica"),
    path("pymes/<int:pyme_id>/", views.pyme_publica, name="pyme_publica"),
    path("pymes/<int:pyme_id>/cotizar/", views.nueva_cotizacion_invitado, name="nueva_cotizacion_invitado"),
    path("cotizacion-publica/<int:pk>/", views.detalle_cotizacion_publica, name="detalle_cotizacion_publica"),
    path("cotizaciones/<int:pk>/enviar/", views.enviar_cotizacion, name="enviar_cotizacion"),
    path("logout/", auth_views.LogoutView.as_view(next_page="cotizador:home_publica"), name="logout"),

    # Auth
    path("login/", views.login_view, name="login"),
    path("registrar/", views.registrar_usuario, name="registrar_usuario"),

    # Privado
    path("dashboard/", views.dashboard, name="dashboard"),

    # ---- MI PYME (AQUÍ LO NUEVO) ----
    path("mi-pyme/seleccionar/", views.seleccionar_pyme, name="seleccionar_pyme"),
    path("mi-pyme/", views.configurar_pyme, name="configurar_pyme"),          # formulario (editar)
    path("mi-pyme/ver/", views.mi_pyme_detalle, name="mi_pyme_detalle"),      # pantalla ver/detalle

    # Vendedores
    path("mi-pyme/vendedores/", views.lista_vendedores, name="lista_vendedores"),
    path("mi-pyme/vendedores/nuevo/", views.crear_vendedor, name="crear_vendedor"),

    # Clientes
    path("clientes/", views.lista_clientes, name="lista_clientes"),
    path("clientes/nuevo/", views.crear_cliente, name="crear_cliente"),
    path("clientes/<int:pk>/editar/", views.editar_cliente, name="editar_cliente"),
    path("clientes/<int:pk>/eliminar/", views.eliminar_cliente, name="eliminar_cliente"),

    # Productos
    path("productos/", views.lista_productos, name="lista_productos"),
    path("productos/nuevo/", views.crear_producto, name="crear_producto"),
    path("productos/<int:pk>/editar/", views.editar_producto, name="editar_producto"),
    path("productos/<int:pk>/eliminar/", views.eliminar_producto, name="eliminar_producto"),

    # Cotizaciones
    path("cotizaciones/", views.lista_cotizaciones, name="lista_cotizaciones"),
    path("cotizaciones/nueva/", views.nueva_cotizacion, name="nueva_cotizacion"),
    path("cotizaciones/<int:pk>/", views.detalle_cotizacion, name="detalle_cotizacion"),

    # Admin sistema
    path("admin/pymes/", views.admin_lista_pymes, name="admin_lista_pymes"),
    path("admin/pymes/nueva/", views.admin_crear_pyme, name="admin_crear_pyme"),
    path("admin/pymes/<int:pk>/editar/", views.admin_editar_pyme, name="admin_editar_pyme"),
    path("admin/pymes/<int:pk>/eliminar/",views.admin_eliminar_pyme,name="admin_eliminar_pyme",
    ),

    # API
    path("api/productos/", views.api_productos, name="api_productos"),
]
