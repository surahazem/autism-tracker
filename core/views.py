from django.shortcuts import render, redirect
from django.db import transaction
from rest_framework.renderers import JSONRenderer
from .models import Parent, User
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.response import Response
from rest_framework import status
from django.contrib import messages
from .serializers import RegistrationSerializer

@api_view(['POST', 'GET'])
@renderer_classes([JSONRenderer])
def register_parent_view(request):

    if request.method == 'GET':
          return render(request, "signup.html")

    serializer = RegistrationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        create_parent_account(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            phone_number=serializer.validated_data.get("phone"),
            address=serializer.validated_data.get("address", ""),
        )
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, "signup.html")

    return redirect("core:login")

@transaction.atomic
def create_parent_account(
    *,
    username: str,
    email: str,
    password: str,
    phone_number: str,
    address: str,
):
    if User.objects.filter(email=email).exists():
        raise ValueError("Email already in use")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )

    parent = Parent.objects.create(
        user=user,
        phone_number=phone_number,
        address=address,
    )

    return parent


