from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    CATEGORY_VEGETABLES = "vegetables"
    CATEGORY_DAIRY = "dairy"
    CATEGORY_BAKERY = "bakery"
    CATEGORY_PRESERVES = "preserves"
    CATEGORY_SEASONAL = "seasonal"

    CATEGORY_CHOICES = [
        (CATEGORY_VEGETABLES, "Vegetables"),
        (CATEGORY_DAIRY, "Dairy"),
        (CATEGORY_BAKERY, "Bakery"),
        (CATEGORY_PRESERVES, "Preserves"),
        (CATEGORY_SEASONAL, "Seasonal Specialities"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=120)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    available_from = models.DateField(blank=True, null=True)
    available_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)  # type: ignore[arg-type]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "name")

    def __str__(self) -> str:  # type: ignore[override]
        return str(self.name)
