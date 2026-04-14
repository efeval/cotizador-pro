from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def home_redirect(request):
    return redirect("/cotizador/")

urlpatterns = [
    path("", home_redirect, name="home"),
    path("admin/", admin.site.urls),
    path("cotizador/", include(("cotizador.urls", "cotizador"), namespace="cotizador")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)