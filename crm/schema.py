# crm/schema.py

import graphene
from graphene_django import DjangoObjectType
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Customer, Product, Order

# Custom Error Type for GraphQL
class CustomErrorType(graphene.ObjectType):
    field = graphene.String()
    message = graphene.String()

# 1. GraphQL Object Types
# These types map our Django models to GraphQL types.

class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone", "created_at")

class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "description", "price", "stock", "created_at")

class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = ("id", "customer", "products", "total_amount", "order_date", "created_at")

# 2. Mutation Classes
# These classes define the operations that modify data.

# == CreateCustomer Mutation ==
class CreateCustomer(graphene.Mutation):
    class Arguments:
        # Input arguments for the mutation
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String()

    # Output fields of the mutation
    customer = graphene.Field(CustomerType)
    message = graphene.String()
    errors = graphene.List(CustomErrorType)

    @staticmethod
    def mutate(root, info, name, email, phone=None):
        try:
            # Basic validation
            if not name.strip():
                raise ValidationError("Name cannot be empty.")
            
            # Use the model's clean_fields to run validators (like validate_phone)
            customer = Customer(name=name, email=email, phone=phone)
            customer.full_clean()  # This runs all model-level validations
            
            # Save if validation passes
            customer.save()
            return CreateCustomer(customer=customer, message="Customer created successfully.")
        
        except ValidationError as e:
            # Handle Django's validation errors
            errors = [CustomErrorType(field=key, message=value[0]) for key, value in e.message_dict.items()]
            return CreateCustomer(errors=errors)
        except Exception as e:
            # Handle other errors like database integrity errors (e.g., duplicate email)
            errors = [CustomErrorType(field="general", message=str(e))]
            return CreateCustomer(errors=errors)


# == BulkCreateCustomers Mutation ==
class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        customers_data = graphene.List(graphene.NonNull(CustomerInput), required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, customers_data):
        successful_customers = []
        error_list = []

        # Use a transaction to ensure atomicity. If anything fails, the whole batch is rolled back.
        # For partial success, we would process them one by one.
        for i, data in enumerate(customers_data):
            try:
                customer = Customer(name=data.name, email=data.email, phone=data.phone)
                customer.full_clean()
                customer.save()
                successful_customers.append(customer)
            except ValidationError as e:
                error_list.append(f"Error on customer #{i+1} ({data.email}): {e.message_dict}")
            except Exception as e:
                error_list.append(f"Error on customer #{i+1} ({data.email}): {str(e)}")

        return BulkCreateCustomers(customers=successful_customers, errors=error_list)


# == CreateProduct Mutation ==
class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Decimal(required=True)
        stock = graphene.Int()

    product = graphene.Field(ProductType)
    errors = graphene.List(CustomErrorType)

    @staticmethod
    def mutate(root, info, name, price, stock=0):
        try:
            if price <= 0:
                raise ValidationError({"price": ["Price must be positive."]})
            if stock < 0:
                 raise ValidationError({"stock": ["Stock cannot be negative."]})
            
            product = Product(name=name, price=price, stock=stock)
            product.full_clean()
            product.save()
            return CreateProduct(product=product)

        except ValidationError as e:
            errors = [CustomErrorType(field=key, message=value[0]) for key, value in e.message_dict.items()]
            return CreateProduct(errors=errors)


# == CreateOrder Mutation ==
class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.NonNull(graphene.ID), required=True)
        order_date = graphene.DateTime()

    order = graphene.Field(OrderType)
    errors = graphene.List(CustomErrorType)

    @staticmethod
    @transaction.atomic
    def mutate(root, info, customer_id, product_ids, order_date=None):
        try:
            # Validate inputs
            if not product_ids:
                raise ValidationError("At least one product must be selected.")

            # Fetch customer
            customer = Customer.objects.filter(pk=customer_id).first()
            if not customer:
                raise ValidationError(f"Invalid customer ID: {customer_id}")

            # Fetch products
            products = Product.objects.filter(pk__in=product_ids)
            if len(products) != len(product_ids):
                found_ids = [str(p.id) for p in products]
                missing_ids = set(product_ids) - set(found_ids)
                raise ValidationError(f"Invalid product IDs: {', '.join(missing_ids)}")

            # Create the order and its relationships within a transaction
            order = Order.objects.create(customer=customer)
            order.products.set(products)
            
            # The save method in the model calculates total_amount
            order.save() 
            
            return CreateOrder(order=order)

        except ValidationError as e:
            # A bit simpler error handling for this one
            return CreateOrder(errors=[CustomErrorType(field="validation", message=str(e))])


# 3. Root Mutation and Query
# This is where we register our mutations.
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()

# We also need a Query class to have a valid schema
class Query(graphene.ObjectType):
    all_customers = graphene.List(CustomerType)
    all_products = graphene.List(ProductType)
    all_orders = graphene.List(OrderType)

    def resolve_all_customers(root, info):
        return Customer.objects.all()

    def resolve_all_products(root, info):
        return Product.objects.all()

    def resolve_all_orders(root, info):
        # Prefetch related objects to avoid N+1 query problem
        return Order.objects.prefetch_related('products').select_related('customer').all()