from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Producer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=100)
    organic = models.BooleanField(default=False)
    postcode = models.CharField(max_length=10)

    class Meta:
        ordering = ("business_name",)

    def __str__(self):
        return self.business_name


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.available_from and self.available_to and self.available_to < self.available_from:
            errors["available_to"] = "Available to date cannot be before available from date."
        if self.harvest_date and self.best_before_date and self.best_before_date < self.harvest_date:
            errors["best_before_date"] = "Best before date cannot be before the harvest date."
        if errors:
            raise ValidationError(errors)


class Product(models.Model):
    producer = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name="products", null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    available_from = models.DateField(blank=True, null=True)
    available_to = models.DateField(blank=True, null=True)
    harvest_date = models.DateField(blank=True, null=True)
    best_before_date = models.DateField(blank=True, null=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    minimum_order_quantity = models.PositiveIntegerField(default=1)
    lead_time_hours = models.PositiveIntegerField(default=48, validators=[MinValueValidator(48)])
    farm_origin = models.CharField(max_length=120, blank=True)
    seasonal_highlight = models.CharField(max_length=120, blank=True)
    storage_guidance = models.TextField(blank=True)
    organic = models.BooleanField(default=False)
    allergen_info = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "name")

    def __str__(self):
        return self.name

    @property
    def available_window(self):
        if self.available_from and self.available_to:
            return f"{self.available_from:%d %b %Y} - {self.available_to:%d %b %Y}"
        if self.available_from:
            return f"From {self.available_from:%d %b %Y}"
        if self.available_to:
            return f"Until {self.available_to:%d %b %Y}"
        return "Available year-round"

    @property
    def is_low_stock(self):
        return self.is_active and 0 < self.stock_quantity <= 5

    @property
    def display_origin(self):
        if self.farm_origin:
            return self.farm_origin
        return self.producer.business_name if self.producer else "Unknown origin"


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    DELIVERY_COLLECTION = "collection"
    DELIVERY_DELIVERY = "delivery"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    DELIVERY_METHOD_CHOICES = [
        (DELIVERY_COLLECTION, "Collection"),
        (DELIVERY_DELIVERY, "Delivery"),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    reference = models.CharField(max_length=20, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    fulfilment_date = models.DateField(blank=True, null=True)
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHOD_CHOICES,
        default=DELIVERY_COLLECTION,
    )
    customer_name = models.CharField(max_length=120, blank=True)
    customer_email = models.EmailField(blank=True)
    delivery_postcode = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"Order {self.pk}"

    @property
    def customer_display_name(self):
        if self.customer_name:
            return self.customer_name
        full_name = self.customer.get_full_name().strip()
        return full_name or self.customer.get_username()

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and not self.reference:
            self.reference = f"ORD-{self.pk:05d}"
            super().save(update_fields=["reference"])


class ProducerSettlement(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
    ]

    producer = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name="settlements")
    week_start = models.DateField()
    week_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payout_reference = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-week_start", "-generated_at")
        constraints = [
            models.UniqueConstraint(fields=["producer", "week_start", "week_end"], name="unique_producer_weekly_settlement"),
        ]

    def __str__(self):
        return f"{self.producer} settlement {self.week_start:%d %b %Y}"

    def recalculate_totals(self):
        aggregates = self.entries.aggregate(
            gross=models.Sum("gross_amount"),
            commission=models.Sum("commission_amount"),
            net=models.Sum("net_amount"),
        )
        self.gross_amount = aggregates["gross"] or Decimal("0.00")
        self.commission_amount = aggregates["commission"] or Decimal("0.00")
        self.net_amount = aggregates["net"] or Decimal("0.00")


class OrderItem(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_PREPARING = "preparing"
    STATUS_READY = "ready"
    STATUS_FULFILLED = "fulfilled"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_READY, "Ready"),
        (STATUS_FULFILLED, "Fulfilled"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    settlement = models.ForeignKey(
        ProducerSettlement,
        on_delete=models.SET_NULL,
        related_name="items",
        blank=True,
        null=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    producer_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("order__created_at", "pk")

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def producer(self):
        return self.product.producer

    @property
    def total_price(self):
        return self.price * self.quantity


class SettlementEntry(models.Model):
    settlement = models.ForeignKey(ProducerSettlement, on_delete=models.CASCADE, related_name="entries")
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="settlement_entry")
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order_item__order__created_at", "pk")

    def __str__(self):
        return f"{self.order_item.order} / {self.order_item.product}"


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    network_commission = models.DecimalField(max_digits=10, decimal_places=2)
    producer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Payment for {self.order}"


class SurplusListing(models.Model):
    producer = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name="surplus_listings")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="surplus_listings")
    quantity = models.PositiveIntegerField(default=1)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discount_percent = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(90)])
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    available_until = models.DateTimeField()
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("available_until", "product__name")

    def __str__(self):
        return f"Surplus: {self.product.name}"

    def clean(self):
        errors = {}
        if self.product_id and self.producer_id and self.product.producer_id != self.producer_id:
            errors["product"] = "You can only create surplus listings for your own products."
        if self.discounted_price is not None and self.original_price is not None and self.discounted_price > self.original_price:
            errors["discounted_price"] = "Discounted price cannot be more than the original price."
        if errors:
            raise ValidationError(errors)


class ProducerContent(models.Model):
    TYPE_RECIPE = "recipe"
    TYPE_STORAGE = "storage"
    TYPE_STORY = "story"

    TYPE_CHOICES = [
        (TYPE_RECIPE, "Seasonal recipe"),
        (TYPE_STORAGE, "Storage guidance"),
        (TYPE_STORY, "Farm story"),
    ]

    producer = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name="content_items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True)
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=140)
    season = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=180, blank=True)
    body = models.TextField()
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("content_type", "-updated_at")

    def __str__(self):
        return self.title

    def clean(self):
        if self.product_id and self.producer_id and self.product.producer_id != self.producer_id:
            raise ValidationError({"product": "You can only link content to your own products."})
