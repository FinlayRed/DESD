from django.contrib import admin

from .models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Producer,
    ProducerContent,
    ProducerSettlement,
    Product,
    SettlementEntry,
    SurplusListing,
)


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
    list_display = (
        "name",
        "category",
        "price",
        "stock_quantity",
        "organic",
        "is_active",
        "producer",
        "updated_at",
    )
    list_filter = ("category", "is_active", "organic")
    search_fields = ("name", "description", "farm_origin", "producer__user__username")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "status", "delivery_method", "paid", "fulfilment_date", "created_at")
    list_filter = ("status", "delivery_method", "paid", "created_at")
    search_fields = ("reference", "customer__username", "customer_name", "delivery_postcode")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "price", "status", "settlement")
    list_filter = ("status", "product")
    search_fields = ("order__reference", "product__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "total_amount", "network_commission", "producer_amount", "created_at")
    search_fields = ("order__reference",)


@admin.register(ProducerSettlement)
class ProducerSettlementAdmin(admin.ModelAdmin):
    list_display = ("producer", "week_start", "week_end", "status", "gross_amount", "net_amount")
    list_filter = ("status", "week_start")
    search_fields = ("producer__business_name", "payout_reference")


@admin.register(SettlementEntry)
class SettlementEntryAdmin(admin.ModelAdmin):
    list_display = ("settlement", "order_item", "gross_amount", "commission_amount", "net_amount")
    search_fields = ("settlement__producer__business_name", "order_item__order__reference", "order_item__product__name")


@admin.register(SurplusListing)
class SurplusListingAdmin(admin.ModelAdmin):
    list_display = ("product", "producer", "quantity", "discount_percent", "discounted_price", "available_until", "is_active")
    list_filter = ("is_active", "available_until")
    search_fields = ("product__name", "producer__business_name", "note")


@admin.register(ProducerContent)
class ProducerContentAdmin(admin.ModelAdmin):
    list_display = ("title", "content_type", "producer", "product", "season", "is_published", "updated_at")
    list_filter = ("content_type", "is_published")
    search_fields = ("title", "summary", "body", "producer__business_name")
