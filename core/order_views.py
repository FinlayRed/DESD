"""
Basket, Checkout, Order and Payment Views
Handles: Shopping cart, multi-vendor checkout, order processing, payment integration
"""

from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView

from .models import Order, OrderItem, Payment, Product, Producer

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
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart
    
    def add(self, product, quantity=1):
        """Add a product to the cart or update quantity."""
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                'quantity': 0,
                'price': str(product.price),
                'producer_id': product.producer.id,
            }
        self.cart[product_id]['quantity'] += quantity
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
                self.cart[product_id]['quantity'] = quantity
            else:
                del self.cart[product_id]
            self.save()
    
    def save(self):
        """Mark the session as modified."""
        self.session.modified = True
    
    def clear(self):
        """Clear the cart."""
        del self.session['cart']
        self.save()
    
    def __iter__(self):
        """Iterate over cart items with full product details."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids).select_related('producer')
        products_dict = {str(p.id): p for p in products}
        
        for product_id, item_data in self.cart.items():
            if product_id in products_dict:
                item = {
                    'product': products_dict[product_id],
                    'quantity': item_data['quantity'],
                    'price': Decimal(item_data['price']),
                    'producer_id': item_data['producer_id'],
                }
                item['total_price'] = item['price'] * item['quantity']
                yield item
    
    def __len__(self):
        """Return total number of items in cart."""
        return sum(item['quantity'] for item in self.cart.values())
    
    @property
    def total_price(self):
        """Calculate total price of all items."""
        return sum(
            Decimal(item['price']) * item['quantity'] 
            for item in self.cart.values()
        )
    
    def get_items_by_producer(self):
        """
        Group cart items by producer for clear supplier separation.
        Required for multi-vendor order transparency.
        """
        producers = {}
        for item in self:
            producer = item['product'].producer
            if producer.id not in producers:
                producers[producer.id] = {
                    'producer': producer,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                }
            producers[producer.id]['items'].append(item)
            producers[producer.id]['subtotal'] += item['total_price']
        return producers
    
    @property
    def is_multi_vendor(self):
        """Check if cart contains products from multiple producers."""
        producer_ids = set(item['producer_id'] for item in self.cart.values())
        return len(producer_ids) > 1
    
    @property
    def producer_count(self):
        """Return number of unique producers in cart."""
        producer_ids = set(item['producer_id'] for item in self.cart.values())
        return len(producer_ids)


# =============================================================================
# CART VIEWS
# =============================================================================

class CartView(TemplateView):
    """
    Display shopping basket with items grouped by producer.
    Shows clear separation of supplier responsibilities.
    """
    template_name = 'core/cart/cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        context['cart'] = cart
        context['items_by_producer'] = cart.get_items_by_producer()
        context['is_multi_vendor'] = cart.is_multi_vendor
        context['producer_count'] = cart.producer_count
        return context

class CartTestView(TemplateView):
    """DEV ONLY: Test page for adding products to cart."""
    template_name = 'core/cart/cart_test.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(is_active=True).select_related('producer')
        return context

class AddToCartView(View):
    """Add a product to the cart."""
    
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart = Cart(request)
        quantity = int(request.POST.get('quantity', 1))
        
        # Check stock availability
        if product.stock_quantity < quantity:
            messages.error(request, f"Only {product.stock_quantity} available.")
            return redirect('core:product-detail', pk=product_id)
        
        cart.add(product, quantity)
        messages.success(request, f"Added {product.name} to your basket.")
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'cart_count': len(cart),
                'cart_total': str(cart.total_price),
            })
        
        return redirect('core:cart')


class UpdateCartView(View):
    """Update quantity of a cart item."""
    
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = Cart(request)
        quantity = int(request.POST.get('quantity', 0))
        
        if quantity > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} available.")
            quantity = product.stock_quantity
        
        cart.update_quantity(product, quantity)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'cart_count': len(cart),
                'cart_total': str(cart.total_price),
            })
        
        return redirect('core:cart')


class RemoveFromCartView(View):
    """Remove a product from the cart."""
    
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = Cart(request)
        cart.remove(product)
        messages.success(request, f"Removed {product.name} from your basket.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'cart_count': len(cart),
                'cart_total': str(cart.total_price),
            })
        
        return redirect('core:cart')



# =============================================================================
# CHECKOUT VIEWS
# =============================================================================

class CheckoutView(LoginRequiredMixin, TemplateView):
    """
    Checkout page with clear multi-vendor order separation.
    Shows each producer's items, responsibilities, and delivery info.
    """
    template_name = 'core/checkout/checkout.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)
        
        if len(cart) == 0:
            return context
        
        context['cart'] = cart
        context['items_by_producer'] = cart.get_items_by_producer()
        context['is_multi_vendor'] = cart.is_multi_vendor
        context['producer_count'] = cart.producer_count
        context['total'] = cart.total_price
        
        # Calculate commission and producer amounts
        commission = cart.total_price * Decimal('0.05')
        context['network_commission'] = commission
        context['producer_total'] = cart.total_price - commission
        
        # Minimum collection date (48hr lead time)
        context['min_collection_date'] = (
            timezone.now() + timezone.timedelta(hours=48)
        ).date()
        
        # Stripe public key for frontend
        context['stripe_public_key'] = getattr(
            settings, 'STRIPE_PUBLIC_KEY', 'pk_test_placeholder'
        )
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Process the order."""
        cart = Cart(request)
        
        if len(cart) == 0:
            messages.error(request, "Your basket is empty.")
            return redirect('core:cart')
        
        # Validate collection date (48hr lead time)
        collection_date_str = request.POST.get('collection_date')
        if collection_date_str:
            from datetime import datetime
            collection_date = datetime.strptime(collection_date_str, '%Y-%m-%d').date()
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
                
                # Store order ID in session for payment processing
                request.session['pending_order_id'] = order.id
                
            return redirect('core:payment', order_id=order.id)
            
        except Exception as e:
            messages.error(request, f"Error creating order: {str(e)}")
            return self.get(request, *args, **kwargs)
    
    def _create_order(self, request, cart):
        """Create order and order items."""
        order = Order.objects.create(
            customer=request.user,
            status=Order.STATUS_PENDING,
            delivery_postcode=request.POST.get('postcode', ''),
            delivery_address=request.POST.get('address', ''),
            collection_date=request.POST.get('collection_date') or None,
        )
        
        # Create order items with traceability snapshot
        for item in cart:
            product = item['product']
            OrderItem.objects.create(
                order=order,
                product=product,
                #producer=product.producer,
                quantity=item['quantity'],
                price=item['price'],
                #product_name=product.name,
                #allergen_info_snapshot=product.allergen_info,
                #best_before_snapshot=getattr(product, 'best_before_date', None),
            )
            
            # Reduce stock
            product.stock_quantity -= item['quantity']
            product.save()
        
        return order
    
    def _create_payment(self, order):
        """Create payment record with 5% commission calculation."""
        total = sum(item.price * item.quantity for item in order.items.all())
        commission = total * Decimal('0.05')
        
        return Payment.objects.create(
            order=order,
            total_amount=total,
            network_commission=commission,
            producer_amount=total - commission,
        )


# =============================================================================
# PAYMENT VIEWS (Stripe Integration)
# =============================================================================

class PaymentView(LoginRequiredMixin, TemplateView):
    """
    Stripe payment page.
    Uses Stripe test/sandbox for development.
    """
    template_name = 'core/checkout/payment.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = kwargs.get('order_id')
        order = get_object_or_404(
            Order, 
            id=order_id, 
            customer=self.request.user,
            status=Order.STATUS_PENDING
        )
        
        context['order'] = order
        context['payment'] = order.payment
        context['items_by_producer'] = self._group_items_by_producer(order)
        context['stripe_public_key'] = getattr(
            settings, 'STRIPE_PUBLIC_KEY', 'pk_test_placeholder'
        )
        
        return context
    
    def _group_items_by_producer(self, order):
        """Group order items by producer for display."""
        producers = {}
        for item in order.items.select_related('producer', 'product'):
            if item.producer.id not in producers:
                producers[item.producer.id] = {
                    'producer': item.product.producer,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                }
            producers[item.producer.id]['items'].append(item)
            producers[item.producer.id]['subtotal'] += item.price * item.quantity
        return producers


class CreatePaymentIntentView(LoginRequiredMixin, View):
    """
    Create Stripe PaymentIntent for secure payment processing.
    Called via AJAX from payment page.
    """
    
    def post(self, request, order_id):
        order = get_object_or_404(
            Order,
            id=order_id,
            customer=request.user,
            status=Order.STATUS_PENDING
        )
        
        try:
            import stripe
            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
            
            # Create PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=int(order.payment.total_amount * 100),  # Stripe uses pence
                currency='gbp',
                metadata={
                    'order_id': order.id,
                    'customer_id': request.user.id,
                },
                # For multi-vendor, we'll use Stripe Connect transfers later
            )
            
            # Store PaymentIntent ID
            order.payment.stripe_payment_intent_id = intent.id
            order.payment.save()
            
            return JsonResponse({
                'client_secret': intent.client_secret,
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """
    Payment success confirmation page.
    Shows order details and producer delivery commitments.
    """
    template_name = 'core/checkout/payment_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = kwargs.get('order_id')
        order = get_object_or_404(
            Order,
            id=order_id,
            customer=self.request.user
        )
        
        context['order'] = order
        context['items_by_producer'] = self._group_items_by_producer(order)
        
        # Clear cart after successful payment
        Cart(self.request).clear()
        
        return context
    
    def _group_items_by_producer(self, order):
        producers = {}
        for item in order.items.select_related('producer'):
            if item.producer.id not in producers:
                producers[item.producer.id] = {
                    'producer': item.producer,
                    'items': [],
                }
            producers[item.producer.id]['items'].append(item)
        return producers


# =============================================================================
# STRIPE WEBHOOK (Payment Confirmation)
# =============================================================================

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    Confirms payment and updates order status.
    """
    import stripe
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle payment success
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        _handle_payment_success(payment_intent)
    
    # Handle payment failure
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        _handle_payment_failure(payment_intent)
    
    return JsonResponse({'status': 'success'})


def _handle_payment_success(payment_intent):
    """
    Process successful payment.
    Updates order status and creates audit trail.
    """
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent['id']
        )
        
        with transaction.atomic():
            # Update payment status
            payment.status = Payment.STATUS_COMPLETED
            payment.stripe_charge_id = payment_intent.get('latest_charge', '')
            payment.completed_at = timezone.now()
            payment.save()
            
            # Update order status
            order = payment.order
            order.status = Order.STATUS_CONFIRMED
            order.confirmed_at = timezone.now()
            order.save()
            
            # TODO: Send notification to producers
            # TODO: Send confirmation email to customer
            
    except Payment.DoesNotExist:
        pass  # Log this error in production


def _handle_payment_failure(payment_intent):
    """Handle failed payment."""
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent['id']
        )
        payment.status = Payment.STATUS_FAILED
        payment.save()
        
    except Payment.DoesNotExist:
        pass


# =============================================================================
# ORDER TRACKING VIEWS
# =============================================================================

class CustomerOrderListView(LoginRequiredMixin, ListView):
    """List customer's orders with status tracking."""
    model = Order
    template_name = 'core/orders/order_list.html'
    context_object_name = 'orders'
    login_url = '/login/'
    
    def get_queryset(self):
        return Order.objects.filter(
            customer=self.request.user
        ).prefetch_related('items__producer').order_by('-created_at')


class CustomerOrderDetailView(LoginRequiredMixin, DetailView):
    """
    Order detail with per-producer responsibility breakdown.
    Shows delivery commitments for each supplier.
    """
    model = Order
    template_name = 'core/orders/order_detail.html'
    context_object_name = 'order'
    login_url = '/login/'
    
    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Group items by producer for clear responsibility display
        producers = {}
        for item in order.items.select_related('producer', 'product'):
            if item.producer.id not in producers:
                producers[item.producer.id] = {
                    'producer': item.product.producer,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                }
            producers[item.producer.id]['items'].append(item)
            producers[item.producer.id]['subtotal'] += item.unit_price * item.quantity
        
        context['items_by_producer'] = producers
        return context


# =============================================================================
# PRODUCER ORDER VIEWS (Order Management)
# =============================================================================

class ProducerOrderListView(LoginRequiredMixin, ListView):
    """
    List orders containing this producer's products.
    Shows order aggregation for multi-vendor orders.
    """
    model = OrderItem
    template_name = 'core/producer/orders.html'
    context_object_name = 'order_items'
    login_url = '/producer/login/'
    
    def get_queryset(self):
        return OrderItem.objects.filter(
            producer__user=self.request.user,
            order__status__in=[
                Order.STATUS_CONFIRMED,
                Order.STATUS_PROCESSING,
                Order.STATUS_READY,
            ]
        ).select_related('order', 'product').order_by('-order__created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group by order for clearer display
        orders = {}
        for item in context['order_items']:
            if item.order.id not in orders:
                orders[item.order.id] = {
                    'order': item.order,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                }
            orders[item.order.id]['items'].append(item)
            orders[item.order.id]['subtotal'] += item.price * item.quantity
        
        context['orders'] = orders
        return context


class ProducerOrderDetailView(LoginRequiredMixin, DetailView):
    """
    Producer's view of an order.
    Shows only their products with delivery commitment info.
    """
    model = Order
    template_name = 'core/producer/order_detail.html'
    context_object_name = 'order'
    login_url = '/producer/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Only show this producer's items
        producer = self.request.user.producer
        items = order.items.filter(producer=producer)
        
        context['items'] = items
        context['subtotal'] = sum(
            item.price * item.quantity for item in items
        )
        context['is_multi_vendor'] = order.items.values('producer').distinct().count() > 1
        
        return context


class UpdateOrderStatusView(LoginRequiredMixin, View):
    """
    Allow producer to update their portion of an order.
    Tracks delivery commitment per supplier.
    """
    login_url = '/producer/login/'
    
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        producer = request.user.producer
        
        # Verify this producer has items in this order
        has_items = order.items.filter(producer=producer).exists()
        if not has_items:
            messages.error(request, "You don't have items in this order.")
            return redirect('core:producer-orders')
        
        new_status = request.POST.get('status')
        
        # For multi-vendor orders, we might need per-producer status tracking
        # For now, if all producers mark ready, update order status
        if new_status == 'ready':
            # TODO: Implement per-producer status tracking for multi-vendor
            # For single-vendor or demo, update order directly
            if order.items.values('producer').distinct().count() == 1:
                order.status = Order.STATUS_READY
                order.save()
                messages.success(request, "Order marked as ready for collection.")
        
        return redirect('core:producer-order-detail', pk=order_id)


