from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "owner", "updated_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description", "owner__username")
