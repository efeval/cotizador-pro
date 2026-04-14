from django.contrib import admin
from .models import Producto, Cliente, Cotizacion, ItemCotizacion

class ItemCotizacionInline(admin.TabularInline):
    model = ItemCotizacion
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'marca', 'precio', 'impuesto', 'activo']
    list_filter = ['tipo', 'activo', 'fecha_creacion']
    search_fields = ['nombre', 'marca', 'descripcion']
    list_editable = ['precio', 'activo']

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'email', 'telefono', 'fecha_creacion']
    search_fields = ['nombre', 'empresa', 'email']
    list_filter = ['fecha_creacion']

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'vendedor', 'estado', 'total', 'fecha_creacion']
    list_filter = ['estado', 'fecha_creacion', 'vendedor']
    search_fields = ['cliente__nombre', 'notas']
    inlines = [ItemCotizacionInline]
    readonly_fields = ['fecha_creacion']

admin.site.register(ItemCotizacion)