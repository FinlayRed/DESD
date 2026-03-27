from django.contrib import admin

from .models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerSettlement,
    Product,
)


@admin.register(Producer)
class ProducerAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "postcode", "organic")
    list_filter = ("organic",)
    search_fields = ("business_name", "user__username", "postcode")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "producer",
        "category",
        "price",
        "stock_quantity",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "organic", "category", "producer")
    search_fields = ("name", "description", "producer__business_name")
    list_editable = ("stock_quantity", "is_active")
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        (None, {
            "fields": ("producer", "category", "name", "description", "price")
        }),
        ("Stock & Availability", {
            "fields": ("stock_quantity", "is_active", "available_from", "available_to")
        }),
        ("Details", {
            "fields": ("organic", "allergen_info")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "status",
        "collection_date",
        "total_display",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("customer__username", "customer__email", "delivery_postcode")
    readonly_fields = ("created_at", "updated_at", "confirmed_at")
    
    fieldsets = (
        (None, {
            "fields": ("customer", "status", "paid")
        }),
        ("Delivery Details", {
            "fields": ("delivery_postcode", "delivery_address", "collection_date")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "confirmed_at"),
            "classes": ("collapse",)
        }),
    )

    def total_display(self, obj):
        return f"£{obj.total_amount}"
    total_display.short_description = "Total"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total_display",)
    
    def line_total_display(self, obj):
        return f"£{obj.line_total}"
    line_total_display.short_description = "Line Total"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "price", "line_total_display")
    list_filter = ("product__producer",)
    search_fields = ("order__id", "product__name")
    
    def line_total_display(self, obj):
        return f"£{obj.line_total}"
    line_total_display.short_description = "Line Total"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "total_amount",
        "network_commission",
        "producer_amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order__id", "stripe_payment_intent_id")
    readonly_fields = ("created_at", "completed_at")


@admin.register(ProducerSettlement)
class ProducerSettlementAdmin(admin.ModelAdmin):
    list_display = (
        "producer",
        "week_starting",
        "week_ending",
        "total_sales",
        "commission_deducted",
        "net_amount",
        "status",
    )
    list_filter = ("status", "producer", "week_starting")
    search_fields = ("producer__business_name",)
    readonly_fields = ("created_at", "paid_at")