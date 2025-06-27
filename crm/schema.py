import graphene
from graphene_django import DjangoObjectType
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
import re
from .models import Customer, Product, Order


# GraphQL Types
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = '__all__'


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = '__all__'


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = '__all__'


# Input Types
class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()


class ProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Decimal(required=True)
    stock = graphene.Int()


class OrderInput(graphene.InputObjectType):
    customerId = graphene.ID(required=True)
    productIds = graphene.List(graphene.ID, required=True)
    order_date = graphene.DateTime()


# Helper Functions
def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return True
    phone_pattern = r'^\+?1?\d{9,15}$|^\d{3}-\d{3}-\d{4}$'
    return bool(re.match(phone_pattern, phone))


def validate_email_unique(email, exclude_id=None):
    """Check if email is unique"""
    query = Customer.objects.filter(email=email)
    if exclude_id:
        query = query.exclude(id=exclude_id)
    return not query.exists()


# Mutations
class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CustomerInput(required=True)

    customer = graphene.Field(CustomerType)
    message = graphene.String()
    success = graphene.Boolean()

    def mutate(self, info, input):
        try:
            # Validate email uniqueness
            if not validate_email_unique(input.email):
                return CreateCustomer(
                    success=False,
                    message="Email already exists"
                )

            # Validate phone format
            if input.phone and not validate_phone(input.phone):
                return CreateCustomer(
                    success=False,
                    message="Invalid phone format. Use +1234567890 or 123-456-7890"
                )

            # Create customer
            customer = Customer.objects.create(
                name=input.name,
                email=input.email,
                phone=input.phone
            )

            return CreateCustomer(
                customer=customer,
                message="Customer created successfully",
                success=True
            )

        except Exception as e:
            return CreateCustomer(
                success=False,
                message=f"Error creating customer: {str(e)}"
            )


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = graphene.List(CustomerInput, required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)
    success = graphene.Boolean()

    def mutate(self, info, input):
        customers = []
        errors = []
        
        try:
            with transaction.atomic():
                for i, customer_data in enumerate(input):
                    try:
                        # Validate email uniqueness
                        if not validate_email_unique(customer_data.email):
                            errors.append(f"Customer {i+1}: Email {customer_data.email} already exists")
                            continue

                        # Validate phone format
                        if customer_data.phone and not validate_phone(customer_data.phone):
                            errors.append(f"Customer {i+1}: Invalid phone format")
                            continue

                        # Create customer
                        customer = Customer.objects.create(
                            name=customer_data.name,
                            email=customer_data.email,
                            phone=customer_data.phone
                        )
                        customers.append(customer)

                    except Exception as e:
                        errors.append(f"Customer {i+1}: {str(e)}")

        except Exception as e:
            errors.append(f"Transaction error: {str(e)}")

        return BulkCreateCustomers(
            customers=customers,
            errors=errors,
            success=len(customers) > 0
        )


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = ProductInput(required=True)

    product = graphene.Field(ProductType)
    message = graphene.String()
    success = graphene.Boolean()

    def mutate(self, info, input):
        try:
            # Validate price
            if input.price <= 0:
                return CreateProduct(
                    success=False,
                    message="Price must be positive"
                )

            # Validate stock
            stock = input.stock if input.stock is not None else 0
            if stock < 0:
                return CreateProduct(
                    success=False,
                    message="Stock cannot be negative"
                )

            # Create product
            product = Product.objects.create(
                name=input.name,
                price=input.price,
                stock=stock
            )

            return CreateProduct(
                product=product,
                message="Product created successfully",
                success=True
            )

        except Exception as e:
            return CreateProduct(
                success=False,
                message=f"Error creating product: {str(e)}"
            )


class CreateOrder(graphene.Mutation):
    class Arguments:
        input = OrderInput(required=True)

    order = graphene.Field(OrderType)
    message = graphene.String()
    success = graphene.Boolean()

    def mutate(self, info, input):
        try:
            # Validate customer exists
            try:
                customer = Customer.objects.get(id=input.customerId)
            except Customer.DoesNotExist:
                return CreateOrder(
                    success=False,
                    message="Customer not found"
                )

            # Validate products exist
            if not input.productIds:
                return CreateOrder(
                    success=False,
                    message="At least one product must be selected"
                )

            products = Product.objects.filter(id__in=input.productIds)
            if len(products) != len(input.productIds):
                return CreateOrder(
                    success=False,
                    message="One or more product IDs are invalid"
                )

            # Create order
            order = Order.objects.create(customer=customer)
            order.products.set(products)
            
            # Calculate total amount
            total = order.calculate_total()
            order.save()

            return CreateOrder(
                order=order,
                message=f"Order created successfully with total amount: ${total}",
                success=True
            )

        except Exception as e:
            return CreateOrder(
                success=False,
                message=f"Error creating order: {str(e)}"
            )


# Query Class
class Query(graphene.ObjectType):
    hello = graphene.String()
    customers = graphene.List(CustomerType)
    products = graphene.List(ProductType)
    orders = graphene.List(OrderType)

    def resolve_hello(self, info):
        return "Hello, GraphQL!"

    def resolve_customers(self, info):
        return Customer.objects.all()

    def resolve_products(self, info):
        return Product.objects.all()

    def resolve_orders(self, info):
        return Order.objects.all()


# Mutation Class
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()