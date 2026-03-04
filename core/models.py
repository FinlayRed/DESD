from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

#Producer model
class Producer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=100)
    organic = models.BooleanField(default=False)
    postcode = models.CharField(max_length=10)

    def __str__(self):
        return self.business_name

#Category model
class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

#Product model
class Product(models.Model):
    CATEGORY_VEGETABLES = "vegetables"
    CATEGORY_DAIRY = "dairy"
    CATEGORY_BAKERY = "bakery"
    CATEGORY_PRESERVES = "preserves"
    CATEGORY_SEASONAL = "seasonal"

    """CATEGORY_CHOICES = [
        (CATEGORY_VEGETABLES, "Vegetables"),
        (CATEGORY_DAIRY, "Dairy"),
        (CATEGORY_BAKERY, "Bakery"),
        (CATEGORY_PRESERVES, "Preserves"),
        (CATEGORY_SEASONAL, "Seasonal Specialities"),
    ]"""

    producer = models.ForeignKey(
        Producer, 
        on_delete=models.CASCADE, 
        related_name="products",
        null=False,
        )
    
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True,
        )

    name = models.CharField(max_length=120)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    available_from = models.DateField(blank=True, null=True)
    available_to = models.DateField(blank=True, null=True)
    organic = models.BooleanField(default=False)
    allergen_info = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)  # type: ignore[arg-type]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "name")

    def __str__(self) -> str:  # type: ignore[override]
        return str(self.name)

class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2) 

class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    network_commission = models.DecimalField(max_digits=10, decimal_places=2)
    producer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)