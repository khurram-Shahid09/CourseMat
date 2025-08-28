from django.db.models import F

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework import generics, permissions
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from student_record.models import Student, Course, Batch, Profile
from ..models import Batch, Enrollment, Teacher, Lesson, Installment
from .filters import EnrollmentFilter, ProfileFilter, InstallmentFilter

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    StudentReadSerializer,
    StudentWriteSerializer,
    CourseReadSerializer,
    CourseWriteSerializer,
    BatchReadSerializer,
    BatchWriteSerializer,
    EnrollmentReadSerializer,
    EnrollmentWriteSerializer,
    TeacherReadSerializer,
    TeacherWriteSerializer,
    LessonReadSerializer,
    LessonWriteSerializer,
    InstallmentReadSerializer,
    InstallmentWriteSerializer,
    ProfileReadSerializer,
    ProfileWriteSerializer,
)

class RegisterAPIView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            student = serializer.save()
            return Response({
                "message": "Registration successful",
                "credentials": student.credentials
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginAPIView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }, status=status.HTTP_200_OK)

class CourseViewSet(ModelViewSet):
    queryset = Course.objects.all().order_by("id")
    filterset_fields = ["title", "level", "course_code", "duration"]
    search_fields = ["title", "course_code", "description"]
    ordering_fields = ["id", "title", "duration", "level"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseWriteSerializer
        return CourseReadSerializer


class StudentViewSet(ModelViewSet):
    queryset = Student.objects.all().order_by("id")
    filterset_fields = ["name", "roll_number", "email", "phone_number", "age"]
    search_fields = ["name", "roll_number", "email", "phone_number"]
    ordering_fields = ["id", "name", "age", "roll_number", "date_of_birth", "email"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return StudentWriteSerializer
        return StudentReadSerializer


class BatchViewSet(ModelViewSet):
    queryset = Batch.objects.all().order_by("id")
    filterset_fields = ["course", "teacher", "number", "start_date", "end_date", "fee"]
    search_fields = ["course__title", "teacher__username", "batch_code"]
    ordering_fields = ["id", "number", "start_date", "end_date", "fee"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BatchWriteSerializer
        return BatchReadSerializer


class EnrollmentViewSet(ModelViewSet):
    queryset = Enrollment.objects.all().order_by("id")
    filterset_fields = ["student", "batch", "status", "fee_type"]
    search_fields = ["student__name", "roll_number", "batch__batch_code", "batch__course__title"]
    ordering_fields = ["id", "enrolled_on", "fee_at_enrollment", "paid_amount"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EnrollmentWriteSerializer
        return EnrollmentReadSerializer


class TeacherViewSet(ModelViewSet):
    queryset = Teacher.objects.all().order_by("id")
    filterset_fields = ["name", "email", "specialization"]
    search_fields = ["name", "email", "teacher_code", "specialization"]
    ordering_fields = ["id", "name", "email"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return TeacherWriteSerializer
        return TeacherReadSerializer


class LessonViewSet(ModelViewSet):
    queryset = Lesson.objects.all().order_by("id")
    filterset_fields = ["course", "batch", "teacher"]
    search_fields = ["title", "content", "teacher__name", "batch__batch_code"]
    ordering_fields = ["id", "created_at", "title"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LessonWriteSerializer
        return LessonReadSerializer


class ProfileViewSet(ModelViewSet):
    queryset = Profile.objects.all().order_by("id")
    search_fields = ["full_name", "user__username", "user__email"]
    ordering_fields = ["id", "full_name"]
    ordering = ["id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return ProfileWriteSerializer
        return ProfileReadSerializer


class InstallmentViewSet(ModelViewSet):
    queryset = Installment.objects.all().order_by("due_date")
    filterset_fields = ["enrollment", "status", "due_date"]
    search_fields = ["enrollment__roll_number", "enrollment__student__name"]
    ordering_fields = ["id", "due_date", "amount", "paid_amount"]
    ordering = ["due_date"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return InstallmentWriteSerializer
        return InstallmentReadSerializer
