from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User as AuthUser  # Utilisateur Django par défaut
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from .models import User, Product, Invoice
from .serializers import UserSerializer, ProductSerializer, InvoiceSerializer
from rest_framework.permissions import IsAuthenticated
from .utils import fetch_product_from_open_food_facts

# ViewSet pour les utilisateurs
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'destroy', 'post']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]


class OpenFoodFactsProductView(APIView):
    """
    Vue pour récupérer les données du produit depuis Open Food Facts.
    """
    def get(self, request, barcode):
        try:
            product_data = fetch_product_from_open_food_facts(barcode)
            if product_data:
                return Response(product_data, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Product not found in Open Food Facts"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "is_admin": request.user.is_admin,
            "is_staff": request.user.is_staff,
            "is_superuser": request.user.is_superuser
        }, status=200)


class KPIView(APIView):
    """
    Generate key performance indicators (KPIs) for managers.
    """
    def get(self, request):
        try:
            # KPI 1: Average purchase amount
            average_purchase = Invoice.objects.aggregate(average_amount=Avg('total_amount'))['average_amount']

            # KPI 2: Total sales
            total_sales = Invoice.objects.aggregate(total_sales=Sum('total_amount'))['total_sales']

            # KPI 3: Most purchased products
            most_purchased_products = (
                Product.objects.annotate(num_invoices=Count('invoice'))
                .order_by('-num_invoices')
                .values('name', 'num_invoices')[:5]
            )

            # KPI 4: Median customer payment (approximated as average for simplicity)
            median_payment = Invoice.objects.aggregate(median_payment=Avg('total_amount'))['median_payment']

            # KPI 5: Number of active customers
            active_customers = Invoice.objects.values('user').distinct().count()

            data = {
                'average_purchase': average_purchase,
                'total_sales': total_sales,
                'most_purchased_products': list(most_purchased_products),
                'median_payment': median_payment,
                'active_customers': active_customers,
            }

            return Response(data, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class RegisterView(APIView):
    permission_classes = [AllowAny]  # Accessible par tous

    def post(self, request):
        try:
            data = request.data

            # Vérifier les champs requis
            required_fields = ['username', 'password', 'first_name', 'last_name', 'phone_number', 'billing_address']
            for field in required_fields:
                if field not in data:
                    return Response({"error": f"Le champ {field} est requis."}, status=status.HTTP_400_BAD_REQUEST)

            # Vérifiez si un utilisateur peut s'inscrire comme admin
            is_admin = data.get('is_admin', False)
            if is_admin:
                # Vérifier si l'utilisateur connecté est un administrateur
                if not request.user.is_authenticated or not request.user.is_admin:
                    return Response({"error": "Vous n'avez pas l'autorisation de créer un administrateur."},
                                    status=status.HTTP_403_FORBIDDEN)

            # Créez l'utilisateur avec les données fournies
            user = User.objects.create(
                username=data['username'],
                email=data.get('email', ''),  # Email facultatif
                password=make_password(data['password']),
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone_number=data['phone_number'],
                billing_address=data['billing_address'],
                is_admin=is_admin
            )
            return Response({"message": "Utilisateur créé avec succès."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
