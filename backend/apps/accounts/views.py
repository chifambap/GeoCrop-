from django.core.mail import send_mail
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, RegistrationRequest
from .serializers import RegisterSerializer, UserSerializer, CustomTokenSerializer


ADMIN_EMAIL = 'pepukaichi@gmail.com'


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
    permission_classes = [permissions.AllowAny]


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()  # created with is_active=False

        RegistrationRequest.objects.create(user=user)
        _send_notification_email(user)

        return Response({
            'detail': 'Registration submitted. Awaiting admin approval.',
            'username': user.username,
        }, status=status.HTTP_201_CREATED)


class PendingRegistrationsView(generics.ListAPIView):
    """Admin only — list pending registration requests."""
    permission_classes = [permissions.IsAdminUser]

    def list(self, request, *args, **kwargs):
        regs = RegistrationRequest.objects.select_related('user').order_by('-created_at')
        data = [{
            'id': reg.id,
            'username': reg.user.username,
            'email': reg.user.email,
            'organisation': reg.user.organisation,
            'created_at': reg.created_at.isoformat(),
        } for reg in regs]
        return Response(data)


class ApproveUserView(APIView):
    """Admin approves a pending registration."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            reg = RegistrationRequest.objects.select_related('user').get(pk=pk)
        except RegistrationRequest.DoesNotExist:
            return Response({'detail': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = reg.user
        user.is_active = True
        user.save()
        reg.delete()

        if user.email:
            send_mail(
                subject='GeoCrop Account Approved',
                message=f'Hi {user.username},\n\nYour GeoCrop account has been approved. You can now log in.\n\n— GeoCrop Team',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

        return Response({'detail': f'User "{user.username}" approved.'})


class RejectUserView(APIView):
    """Admin rejects a pending registration."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            reg = RegistrationRequest.objects.select_related('user').get(pk=pk)
        except RegistrationRequest.DoesNotExist:
            return Response({'detail': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

        username = reg.user.username
        email = reg.user.email

        if email:
            send_mail(
                subject='GeoCrop Registration Declined',
                message=f'Hi {username},\n\nYour GeoCrop registration request has been declined.\n\n— GeoCrop Team',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )

        reg.user.delete()  # cascades to RegistrationRequest
        return Response({'detail': f'User "{username}" rejected.'})


class LogoutView(APIView):
    def post(self, request):
        try:
            token = RefreshToken(request.data['refresh'])
            token.blacklist()
            return Response({'detail': 'Successfully logged out.'})
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """Admin only — list all users."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]


def _send_notification_email(user):
    send_mail(
        subject=f'GeoCrop: New registration request from {user.username}',
        message=(
            f'New user registration request:\n\n'
            f'  Username:     {user.username}\n'
            f'  Email:        {user.email}\n'
            f'  Organisation: {user.organisation or "—"}\n\n'
            f'Log in to the GeoCrop dashboard to approve or reject this request.\n'
            f'https://geos.zingsageocrops.com/dashboard/\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[ADMIN_EMAIL],
        fail_silently=True,
    )
