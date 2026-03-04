from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "producer", "updated_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description", "producer__username")

    def producer_username(self, obj):
        return obj.producer.user.username
    producer_username.short_description = "Producer username"

