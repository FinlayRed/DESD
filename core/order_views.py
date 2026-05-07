"""
Basket, Checkout, Order and Payment Views
Bristol Regional Food Network - John's Implementation
"""

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView

from .models import Order, OrderItem, Payment, Product
from .traceability import create_traceability_records


# =============================================================================
# CART SESSION MANAGEMENT
# =============================================================================

class Cart:
    """
    Shopping cart stored in session.
    Supports multi-vendor orders with clear supplier separation.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get("cart")
        if not cart:
            cart = self.session["cart"] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        """Add a product to the cart or update quantity."""
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                "quantity": 0,
                "price": str(product.price),
                "producer_id": product.producer.id,
            }
        self.cart[product_id]["quantity"] += quantity
        self.save()

    def remove(self, product):
        """Remove a product from the cart."""
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def update_quantity(self, product, quantity):
        """Update quantity of a product."""
        product_id = str(product.id)
        if product_id in self.cart:
            if quantity > 0:
                self.cart[product_id]["quantity"] = quantity
            else:
                del self.cart[product_id]
            self.save()

    def save(self):
        """Mark the session as modified."""
        self.session.modified = True

    def clear(self):
        """Clear the cart."""
        del self.session["cart"]
        self.save()

    def __iter__(self):
        """Iterate over cart items with full product details."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids).select_related("producer")
        products_dict = {str(p.id): p for p in products}

        for product_id, item_data in self.cart.items():
            if product_id in products_dict:
                item = {
                    "product": products_dict[product_id],
                    "quantity": item_data["quantity"],
                    "price": Decimal(item_data["price"]),
                    "producer_id": item_data["producer_id"],
                }
                item["total_price"] = item["price"] * item["quantity"]
                yield item

    def __len__(self):
        """Return total number of items in cart."""
        return sum(item["quantity"] for item in self.cart.values())

    @property
    def total_price(self):
        """Calculate total price of all items."""
        return sum(
            Decimal(item["price"]) * item["quantity"]
            for item in self.cart.values()
        )

    def get_items_by_producer(self):
        """
        Group cart items by producer for clear supplier separation.
        Required for multi-vendor order transparency.
        """
        producers = {}
        for item in self:
            producer = item["product"].producer
            if producer.id not in producers:
                producers[producer.id] = {
                    "producer": producer,
                    "items": [],
                    "subtotal": Decimal("0.00"),
                }
            producers[producer.id]["items"].append(item)
            producers[producer.id]["subtotal"] += item["total_price"]
        return producers

    @property
    def is_multi_vendor(self):
        """Check if cart contains products from multiple producers."""
        producer_ids = set(item["producer_id"] for item in self.cart.values())
        return len(producer_ids) > 1

    @property
    def producer_count(self):
        """Return number of unique producers in cart."""
        producer_ids = set(item["producer_id"] for item in self.cart.values())
        return len(producer_ids)


# =============================================================================
# CART VIEWS
# =============================================================================

class CartView(TemplateView):
    """
    Display shopping basket with items grouped by producer.
    """
    template_name = "core/cart/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        context["cart"] = cart
        context["items_by_producer"] = cart.get_items_by_producer()
        context["is_multi_vendor"] = cart.is_multi_vendor
        context["producer_count"] = cart.producer_count
        return context


class CartTestView(TemplateView):
    """DEV ONLY: Test page for adding products to cart."""
    template_name = "core/cart/cart_test.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["products"] = Product.objects.filter(
            is_active=True,
            stock_quantity__gt=0
        ).select_related("producer")
        return context


class AddToCartView(View):
    """Add a product to the cart."""

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart = Cart(request)
        quantity = int(request.POST.get("quantity", 1))

        # Check stock availability
        if product.stock_quantity < quantity:
            messages.error(request, f"Only {product.stock_quantity} available.")
            return redirect("core:cart")

        cart.add(product, quantity)
        messages.success(request, f"Added {product.name} to your basket.")

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "cart_count": len(cart),
                "cart_total": str(cart.total_price),
            })

        return redirect("core:cart")


class UpdateCartView(View):
    """Update quantity of a cart item."""

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = Cart(request)
        quantity = int(request.POST.get("quantity", 0))

        if quantity > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} available.")
            quantity = product.stock_quantity

        cart.update_quantity(product, quantity)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "cart_count": len(cart),
                "cart_total": str(cart.total_price),
            })

        return redirect("core:cart")


class RemoveFromCartView(View):
    """Remove a product from the cart."""

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = Cart(request)
        cart.remove(product)
        messages.success(request, f"Removed {product.name} from your basket.")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "cart_count": len(cart),
                "cart_total": str(cart.total_price),
            })

        return redirect("core:cart")


# =============================================================================
# CHECKOUT VIEWS
# =============================================================================

class CheckoutView(LoginRequiredMixin, TemplateView):
    """
    Checkout page with multi-vendor order separation and 48hr lead time.
    """
    template_name = "core/checkout/checkout.html"
    login_url = "/customer/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)

        if len(cart) == 0:
            return context

        context["cart"] = cart
        context["items_by_producer"] = cart.get_items_by_producer()
        context["is_multi_vendor"] = cart.is_multi_vendor
        context["producer_count"] = cart.producer_count
        context["total"] = cart.total_price

        # Calculate commission and producer amounts
        commission = cart.total_price * Decimal("0.05")
        context["network_commission"] = commission
        context["producer_total"] = cart.total_price - commission

        # Minimum collection date (48hr lead time - BRFN requirement)
        context["min_collection_date"] = (
            timezone.now() + timezone.timedelta(hours=48)
        ).date()

        return context

    def post(self, request, *args, **kwargs):
        """Process the order."""
        cart = Cart(request)

        if len(cart) == 0:
            messages.error(request, "Your basket is empty.")
            return redirect("core:cart")

        # Validate collection date (48hr lead time)
        collection_date_str = request.POST.get("collection_date")
        if collection_date_str:
            from datetime import datetime
            collection_date = datetime.strptime(collection_date_str, "%Y-%m-%d").date()
            min_date = (timezone.now() + timezone.timedelta(hours=48)).date()
            if collection_date < min_date:
                messages.error(
                    request,
                    f"Collection date must be at least 48 hours from now ({min_date})."
                )
                return self.get(request, *args, **kwargs)

        # Create order with transaction
        try:
            with transaction.atomic():
                order = self._create_order(request, cart)
                payment = self._create_payment(order)

            return redirect("core:payment", order_id=order.id)

        except Exception as e:
            messages.error(request, f"Error creating order: {str(e)}")
            return self.get(request, *args, **kwargs)

    def _create_order(self, request, cart):
        """Create order and order items."""
        order = Order.objects.create(
            customer=request.user,
            status=Order.STATUS_PENDING,
            customer_name=request.user.get_full_name(),
            customer_email=request.user.email,
            delivery_postcode=request.POST.get("postcode", ""),
            delivery_address=request.POST.get("address", ""),
            collection_date=request.POST.get("collection_date") or None,
            fulfilment_date=request.POST.get("collection_date") or None,
        )

        # Create order items
        for item in cart:
            product = item["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item["quantity"],
                price=item["price"],
            )

            # Reduce stock
            product.stock_quantity -= item["quantity"]
            product.save()

        return order

    def _create_payment(self, order):
        """Create payment record with 5% commission calculation."""
        total = sum(item.line_total for item in order.items.all())
        commission = total * Decimal("0.05")

        return Payment.objects.create(
            order=order,
            total_amount=total,
            network_commission=commission,
            producer_amount=total - commission,
        )


# =============================================================================
# PAYMENT VIEWS
# =============================================================================

class PaymentView(LoginRequiredMixin, TemplateView):
    """
    Payment page (Stripe-ready for future integration).
    """
    template_name = "core/checkout/payment.html"
    login_url = "/customer/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = kwargs.get("order_id")
        order = get_object_or_404(
            Order,
            id=order_id,
            customer=self.request.user,
            status=Order.STATUS_PENDING,
        )

        context["order"] = order
        context["payment"] = order.payment
        context["items_by_producer"] = self._group_items_by_producer(order)
        context["stripe_public_key"] = getattr(
            settings, "STRIPE_PUBLIC_KEY", "pk_test_placeholder"
        )

        return context

    def _group_items_by_producer(self, order):
        """Group order items by producer for display."""
        producers = {}
        for item in order.items.select_related("product__producer"):
            producer = item.product.producer
            if producer.id not in producers:
                producers[producer.id] = {
                    "producer": producer,
                    "items": [],
                    "subtotal": Decimal("0.00"),
                }
            producers[producer.id]["items"].append(item)
            producers[producer.id]["subtotal"] += item.line_total
        return producers


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """Order confirmation page after successful payment."""
    template_name = "core/checkout/payment_success.html"
    login_url = "/customer/login/"

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(
            Order,
            id=kwargs.get("order_id"),
            customer=request.user,
        )
        payment = getattr(order, "payment", None)
        if payment and payment.status != Payment.STATUS_COMPLETED:
            payment.status = Payment.STATUS_COMPLETED
            payment.completed_at = timezone.now()
            payment.save(update_fields=["status", "completed_at"])
        if not order.paid or order.status == Order.STATUS_PENDING:
            order.paid = True
            order.status = Order.STATUS_CONFIRMED
            order.confirmed_at = timezone.now()
            order.save(update_fields=["paid", "status", "confirmed_at", "updated_at"])
            create_traceability_records(order)

        # Clear the cart after successful payment
        cart = Cart(request)
        try:
            cart.clear()
        except KeyError:
            pass  # Cart already empty
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = kwargs.get("order_id")
        order = get_object_or_404(
            Order,
            id=order_id,
            customer=self.request.user,
        )
        context["order"] = order
        return context


# =============================================================================
# CUSTOMER ORDER VIEWS
# =============================================================================

class CustomerOrderListView(LoginRequiredMixin, ListView):
    """List customer's orders with status tracking."""
    model = Order
    template_name = "core/orders/order_list.html"
    context_object_name = "orders"
    login_url = "/customer/login/"

    def get_queryset(self):
        return Order.objects.filter(
            customer=self.request.user
        ).prefetch_related("items__product__producer").order_by("-created_at")


class CustomerOrderDetailView(LoginRequiredMixin, DetailView):
    """Order detail with per-producer breakdown."""
    model = Order
    template_name = "core/orders/order_detail.html"
    context_object_name = "order"
    login_url = "/customer/login/"

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Group items by producer
        producers = {}
        for item in order.items.select_related("product__producer", "traceability_record"):
            producer = item.product.producer
            if producer.id not in producers:
                producers[producer.id] = {
                    "producer": producer,
                    "items": [],
                    "subtotal": Decimal("0.00"),
                }
            producers[producer.id]["items"].append(item)
            producers[producer.id]["subtotal"] += item.line_total

        context["items_by_producer"] = producers
        return context


# =============================================================================
# PRODUCER ORDER VIEWS
# =============================================================================

class ProducerOrderListView(LoginRequiredMixin, ListView):
    """List orders containing this producer's products."""
    model = OrderItem
    template_name = "core/producer/orders.html"
    context_object_name = "order_items"
    login_url = "/producer/login/"

    def get_queryset(self):
        return OrderItem.objects.filter(
            product__producer__user=self.request.user,
            order__status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_PROCESSING,
                Order.STATUS_READY,
            ]
        ).select_related("order", "product").order_by("-order__created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Group by order for clearer display
        orders = {}
        for item in context["order_items"]:
            if item.order.id not in orders:
                orders[item.order.id] = {
                    "order": item.order,
                    "items": [],
                    "subtotal": Decimal("0.00"),
                }
            orders[item.order.id]["items"].append(item)
            orders[item.order.id]["subtotal"] += item.line_total

        context["orders"] = orders
        return context


class ProducerOrderDetailView(LoginRequiredMixin, DetailView):
    """Producer's view of an order - shows only their products."""
    model = Order
    template_name = "core/producer/order_detail.html"
    context_object_name = "order"
    login_url = "/producer/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Only show this producer's items
        items = order.items.filter(
            product__producer__user=self.request.user
        ).select_related("product")

        context["items"] = items
        context["subtotal"] = sum(item.line_total for item in items)
        context["is_multi_vendor"] = order.is_multi_vendor

        return context


class UpdateOrderStatusView(LoginRequiredMixin, View):
    """Allow producer to update their portion of an order."""
    login_url = "/producer/login/"

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)

        # Verify this producer has items in this order
        has_items = order.items.filter(
            product__producer__user=request.user
        ).exists()

        if not has_items:
            messages.error(request, "You don't have items in this order.")
            return redirect("core:order-list")

        new_status = request.POST.get("status")

        if new_status == "ready":
            # For single-vendor orders, update directly
            if not order.is_multi_vendor:
                order.status = Order.STATUS_READY
                order.save()
                messages.success(request, "Order marked as ready for collection.")

        return redirect("core:order-detail", pk=order_id)


# =============================================================================
# STRIPE WEBHOOK (Placeholder)
# =============================================================================

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    Placeholder for future Stripe integration.
    """
    # TODO: Implement actual Stripe webhook handling
    return JsonResponse({"status": "received"})
