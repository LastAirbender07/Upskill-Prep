from enum import Enum


class AccountStatus(str, Enum):
    active = 'active'
    suspended = 'suspended'
    closed = 'closed'


class ProductCategory(str, Enum):
    electronics = 'electronics'
    clothing = 'clothing'
    food = 'food'
    miscellaneous = 'miscellaneous'


class ProductStatus(str, Enum):
    available = 'available'
    out_of_stock = 'out_of_stock'
    discontinued = 'discontinued'


class OrderStatus(str, Enum):
    pending = 'pending'
    confirmed = 'confirmed'
    processing = 'processing'
    shipped = 'shipped'
    delivered = 'delivered'
    cancelled = 'cancelled'
    refunded = 'refunded'


class PaymentStatus(str, Enum):
    pending = 'pending'
    processing = 'processing'      # added — state between pending and resolved
    completed = 'completed'
    failed = 'failed'
    refunded = 'refunded'


class PaymentMethod(str, Enum):
    card = 'card'
    bank_transfer = 'bank_transfer'
    wallet = 'wallet'


class ShipmentCarrier(str, Enum):
    fedex = 'fedex'
    ups = 'ups'
    dhl = 'dhl'
    local_courier = 'local_courier'


class ShipmentStatus(str, Enum):
    preparing = 'preparing'
    dispatched = 'dispatched'
    in_transit = 'in_transit'
    delivered = 'delivered'
    returned = 'returned'


class EventType(str, Enum):
    order_created = 'order_created'
    order_confirmed = 'order_confirmed'
    order_cancelled = 'order_cancelled'
    order_shipped = 'order_shipped'
    order_delivered = 'order_delivered'
    payment_completed = 'payment_completed'
    payment_failed = 'payment_failed'
    payment_refunded = 'payment_refunded'
    shipment_dispatched = 'shipment_dispatched'
    shipment_delivered = 'shipment_delivered'
    customer_suspended = 'customer_suspended'


class AggregateType(str, Enum):
    order = 'order'
    payment = 'payment'
    customer = 'customer'
    shipment = 'shipment'
