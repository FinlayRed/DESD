from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Producer(models.Model):
    """
    Local food producer/supplier within 20-mile Bristol radius.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=100)
    organic = models.BooleanField(default=False)
    postcode = models.CharField(max_length=10)

    def __str__(self):
        return self.business_name


class Category(models.Model):
    """
    Product categories: Vegetables, Dairy, Bakery, Preserves, Seasonal Specialities.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Products offered by local producers.
    Includes seasonal availability and stock tracking.
    """
    producer = models.ForeignKey(
        Producer,
        on_delete=models.CASCADE,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    
    # Stock tracking (BRFN requirement)
    stock_quantity = models.PositiveIntegerField(default=0)
    
    # Seasonal availability
    available_from = models.DateField(blank=True, null=True)
    available_to = models.DateField(blank=True, null=True)
    
    # Product details
    organic = models.BooleanField(default=False)
    allergen_info = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "name")

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        """Check if product is in stock and active."""
        return self.is_active and self.stock_quantity > 0

    @property
    def is_in_season(self):
        """Check if product is currently in season."""
        today = timezone.localdate()
        if self.available_from and self.available_to:
            return self.available_from <= today <= self.available_to
        return True  # No dates set = always available


class Order(models.Model):
    """
    Customer order - may contain items from multiple producers (multi-vendor).
    """
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PROCESSING = "processing"
    STATUS_READY = "ready"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Payment"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_READY, "Ready for Collection"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    
    # Delivery details
    delivery_postcode = models.CharField(max_length=10, blank=True)
    delivery_address = models.TextField(blank=True)
    
    # Collection date with 48hr lead time (BRFN requirement)
    collection_date = models.DateField(null=True, blank=True)
    
    # Legacy field for compatibility
    paid = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"

    @property
    def total_amount(self):
        """Calculate total order amount from items."""
        return sum(item.line_total for item in self.items.all())

    @property
    def is_multi_vendor(self):
        """Check if order contains products from multiple producers."""
        producer_ids = self.items.values_list(
            'product__producer_id', flat=True
        ).distinct()
        return producer_ids.count() > 1

    @property
    def minimum_collection_date(self):
        """48-hour lead time requirement."""
        return (timezone.now() + timezone.timedelta(hours=48)).date()


class OrderItem(models.Model):
    """
    Individual item within an order.
    Links to product for traceability.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,  # Prevent deletion of products with orders
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def line_total(self):
        """Calculate line total for this item."""
        return self.price * self.quantity

    @property
    def producer(self):
        """Access producer through product for convenience."""
        return self.product.producer


class Payment(models.Model):
    """
    Payment record with 5% network commission (BRFN requirement).
    """
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    COMMISSION_RATE = Decimal("0.05")  # 5% network commission

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    network_commission = models.DecimalField(max_digits=10, decimal_places=2)
    producer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    
    # Stripe fields (for future integration)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for Order #{self.order_id} - £{self.total_amount}"

    def save(self, *args, **kwargs):
        """Auto-calculate commission on save if not set."""
        if self.network_commission is None:
            self.network_commission = self.total_amount * self.COMMISSION_RATE
        if self.producer_amount is None:
            self.producer_amount = self.total_amount - self.network_commission
        super().save(*args, **kwargs)


class ProducerSettlement(models.Model):
    """
    Weekly settlement record for producer payments (BRFN requirement).
    Network pays producers weekly minus 5% commission.
    """
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
    ]

    producer = models.ForeignKey(
        Producer,
        on_delete=models.CASCADE,
        related_name="settlements",
    )
    week_starting = models.DateField()
    week_ending = models.DateField()
    
    total_sales = models.DecimalField(max_digits=10, decimal_places=2)
    commission_deducted = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    
    # Payment tracking
    stripe_transfer_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_starting"]
        unique_together = ["producer", "week_starting"]

    def __str__(self):
        return f"{self.producer.business_name} - Week of {self.week_starting}"