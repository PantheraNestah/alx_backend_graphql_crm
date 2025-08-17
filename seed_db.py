import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alx_backend_graphql_crm.settings")
django.setup()

from crm.models import Customer, Product

def run():
    Customer.objects.all().delete()
    Product.objects.all().delete()

    customers = [
        Customer(name="Alice", email="alice@example.com", phone="+1234567890"),
        Customer(name="Bob", email="bob@example.com"),
    ]
    Customer.objects.bulk_create(customers)

    products = [
        Product(name="Laptop", price=999.99, stock=10),
        Product(name="Phone", price=499.99, stock=20),
    ]
    Product.objects.bulk_create(products)

    print("Database seeded successfully!")

if __name__ == "__main__":
    run()