from django.contrib import admin

from .models import Category, Order, OrderItem, Payment, Producer, Product


@admin.register(Producer)
class ProducerAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "organic", "postcode")
    list_filter = ("organic",)
    search_fields = ("business_name", "user__username", "postcode")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "producer", "updated_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description", "producer__user__username")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "paid", "created_at", "updated_at")
    list_filter = ("paid", "created_at")
    search_fields = ("customer__username",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "price")
    list_filter = ("product",)
    search_fields = ("order__id", "product__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "total_amount", "network_commission", "producer_amount", "created_at")
    search_fields = ("order__id",)
