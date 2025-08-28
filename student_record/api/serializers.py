from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.timezone import now

from dateutil.relativedelta import relativedelta

from student_record.models import (
    Student,
    Course,
    Batch,
    Enrollment,
    Teacher,
    Lesson,
    Profile,
    Installment,
    LessonImage,
)

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    age = serializers.IntegerField(required=False)
    phone_number = serializers.CharField(max_length=20, required=False)
    date_of_birth = serializers.DateField(required=False)
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        name = validated_data['name']
        email = validated_data['email']
        password = validated_data['password1']
        username = email.split('@')[0]

        # Create User
        user = User.objects.create_user(username=username, email=email, password=password)

        # Create Profile
        Profile.objects.create(user=user, full_name=name, role="student")

        # Create Student
        student = Student.objects.create(
            user=user,
            name=name,
            age=validated_data.get('age'),
            email=email,
            phone_number=validated_data.get('phone_number'),
            date_of_birth=validated_data.get('date_of_birth'),
        )

        student.credentials = {"username": username, "password": password}
        return student

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True)

class StudentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "roll_number", "name", "age", "email", "phone_number", "date_of_birth"]
        read_only_fields = ["roll_number", "id"]


class StudentWriteSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=Student.objects.all(), message="This email is already used.")]
    )

    class Meta:
        model = Student
        fields = ["name", "age", "email", "phone_number", "date_of_birth"]

    def create(self, validated_data):
        email = validated_data['email']
        name = validated_data['name']

        # Generate username & password
        username = email.split("@")[0]
        password = f"{username}123"

        # Create user and profile
        user = User.objects.create_user(username=username, email=email, password=password)
        Profile.objects.create(user=user, full_name=name, role="student")

        # Create student record
        student = Student.objects.create(user=user, **validated_data)
        student.credentials = {"username": username, "password": password}

        return student

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CourseReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title", "description", "duration", "level", "course_code"]
        read_only_fields = ["course_code", "id"]


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["title", "description", "duration", "level"]


# Batch read serializer
class BatchReadSerializer(serializers.ModelSerializer):
    course = serializers.StringRelatedField()
    teacher = serializers.StringRelatedField()

    class Meta:
        model = Batch
        fields = [
            'id',
            'course',
            'teacher',
            'number',
            'start_date',
            'end_date',
            'fee',
            'batch_code',
            'created_at',
        ]
        read_only_fields = ['batch_code', 'created_at', 'number']


# Batch write serializer
class BatchWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ['course', 'teacher', 'start_date', 'end_date', 'fee']

    def validate(self, attrs):
        start = attrs.get('start_date')
        end = attrs.get('end_date')
        course = attrs.get('course')

        if start and end and start >= end:
            raise serializers.ValidationError("Start date must be before end date.")

        if course:
            today = timezone.now().date()
            active_batches = Batch.objects.filter(course=course, end_date__gte=today)
            if self.instance:
                active_batches = active_batches.exclude(pk=self.instance.pk)
            if active_batches.count() >= 3:
                raise serializers.ValidationError(
                    f"Course '{course.title}' already has 3 active batches."
                )

        return attrs

    def create(self, validated_data):
        course = validated_data['course']
        today = timezone.now().date()
        active_batches = Batch.objects.filter(course=course, end_date__gte=today).order_by('number')
        existing_numbers = list(active_batches.values_list('number', flat=True))

        # Assign first available number (1-3)
        for num in range(1, 4):
            if num not in existing_numbers:
                validated_data['number'] = num
                break
        else:
            raise serializers.ValidationError(
                f"Course '{course.title}' already has 3 active batches."
            )

        batch = Batch.objects.create(**validated_data)
        return batch


# Read / List serializer
class EnrollmentReadSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    batch_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    pending_amount = serializers.ReadOnlyField()
    is_fully_paid = serializers.ReadOnlyField()

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'student',
            'student_name',
            'batch',
            'batch_code',
            'course_title',
            'enrolled_on',
            'status',
            'fee_type',
            'fee_at_enrollment',
            'paid_amount',
            'roll_number',
            'pending_amount',
            'is_fully_paid',
        ]
        read_only_fields = ['roll_number', 'pending_amount', 'is_fully_paid', 'enrolled_on']

    def get_student_name(self, obj):
        return obj.student.name if obj.student else None

    def get_batch_code(self, obj):
        return obj.batch.batch_code if obj.batch else None

    def get_course_title(self, obj):
        return obj.batch.course.title if obj.batch and obj.batch.course else None


# Create / Update serializer
class EnrollmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ['student', 'batch', 'status', 'fee_type', 'fee_at_enrollment', 'paid_amount']
        read_only_fields = ['fee_at_enrollment', 'paid_amount', 'roll_number', 'enrolled_on']

    def validate(self, attrs):
        student = attrs.get('student')
        batch = attrs.get('batch')

        if not student or not batch:
            raise serializers.ValidationError("Both student and batch are required.")

        # Check student max 3 courses
        enrolled_courses = Enrollment.objects.filter(student=student).values_list('batch__course', flat=True).distinct()
        if len(enrolled_courses) >= 3:
            raise serializers.ValidationError(f"{student.name} is already enrolled in 3 courses.")

        # Prevent enrolling in same course twice
        if Enrollment.objects.filter(student=student, batch__course=batch.course).exists():
            raise serializers.ValidationError(f"{student.name} is already enrolled in {batch.course.title}.")

        # Check batch capacity
        if batch.enrollments.count() >= 10:
            raise serializers.ValidationError(f"Batch {batch.number} of {batch.course.title} is already full.")

        return attrs

    def create(self, validated_data):
        # Automatically set fee_at_enrollment and initial paid_amount if needed
        batch = validated_data['batch']
        if 'fee_at_enrollment' not in validated_data or not validated_data['fee_at_enrollment']:
            validated_data['fee_at_enrollment'] = batch.fee
        if 'paid_amount' not in validated_data or not validated_data['paid_amount']:
            validated_data['paid_amount'] = 0

        enrollment = Enrollment.objects.create(**validated_data)
        return enrollment


class TeacherReadSerializer(serializers.ModelSerializer):
    course_titles = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            'id',
            'user',
            'user_email',
            'name',
            'email',
            'phone',
            'specialization',
            'teacher_code',
            'courses',
            'course_titles',
        ]
        read_only_fields = ['teacher_code', 'user', 'email', 'course_titles', 'user_email']

    def get_course_titles(self, obj):
        return [course.title for course in obj.courses.all()]

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None


# Teacher write serializer (for create/update)
class TeacherWriteSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    courses = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True)
    credentials = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Teacher
        fields = ['name', 'email', 'phone', 'specialization', 'courses', 'credentials']

    def create(self, validated_data):
        email = validated_data.pop('email')
        name = validated_data.pop('name')
        courses = validated_data.pop('courses', [])

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        username = email.split("@")[0]
        password = f"{username}123"

        user = User.objects.create_user(username=username, email=email, password=password)
        Profile.objects.create(user=user, full_name=name, role="teacher")

        teacher = Teacher.objects.create(user=user, name=name, email=email, **validated_data)
        teacher.courses.set(courses)
        teacher.credentials = {"username": username, "password": password}
        return teacher

    def get_credentials(self, obj):
        return getattr(obj, 'credentials', None)

    def update(self, instance, validated_data):
        courses = validated_data.pop('courses', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if courses is not None:
            instance.courses.set(courses)
        instance.save()
        return instance


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'name', 'roll_number', 'email']


class LessonReadSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    batch_code = serializers.CharField(source='batch.batch_code', read_only=True)
    students = serializers.SerializerMethodField()
    student_names = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'content', 'teacher', 'teacher_name',
            'course', 'batch', 'batch_code', 'students', 'student_names', 'created_at'
        ]
        read_only_fields = ['created_at', 'batch_code', 'teacher_name', 'student_names']

    def get_teacher_name(self, obj):
        return obj.teacher.name if obj.teacher else None

    def get_students(self, obj):
        if obj.batch:
            return StudentSerializer(
                Student.objects.filter(enrollments__batch=obj.batch).distinct(),
                many=True
            ).data
        return []

    def get_student_names(self, obj):
        return [s['name'] for s in self.get_students(obj)]


# Lesson write serializer (create / update)
class LessonWriteSerializer(serializers.ModelSerializer):
    students = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Student.objects.all(), required=False
    )
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Lesson
        fields = ['title', 'content', 'teacher', 'course', 'batch', 'students', 'images']

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        students_data = validated_data.pop('students', [])

        user = self.context.get('request').user
        teacher = getattr(user, 'teacher_profile', None)

        if teacher:
            validated_data['teacher'] = teacher

        lesson = Lesson.objects.create(**validated_data)

        if students_data:
            lesson.students.set(students_data)

        for img in images_data:
            LessonImage.objects.create(lesson=lesson, image=img)

        return lesson

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', [])
        students_data = validated_data.pop('students', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if students_data is not None:
            instance.students.set(students_data)

        for img in images_data:
            LessonImage.objects.create(lesson=instance, image=img)

        return instance


# Profile read serializer
class ProfileReadSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user', 'username', 'email', 'role', 'full_name']
        read_only_fields = ['username', 'email']


# Profile write serializer (update only)
class ProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['role', 'full_name']


# Installment read serializer
class InstallmentReadSerializer(serializers.ModelSerializer):
    enrollment_roll_number = serializers.CharField(source='enrollment.roll_number', read_only=True)
    student_name = serializers.CharField(source='enrollment.student.name', read_only=True)
    batch_code = serializers.CharField(source='enrollment.batch.batch_code', read_only=True)

    class Meta:
        model = Installment
        fields = [
            'id',
            'enrollment',
            'enrollment_roll_number',
            'student_name',
            'batch_code',
            'due_date',
            'amount',
            'paid_amount',
            'status',
            'paid_date',
        ]
        read_only_fields = ['enrollment_roll_number', 'student_name', 'batch_code']


# Installment write serializer
class InstallmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Installment
        fields = ['enrollment', 'due_date', 'amount', 'paid_amount', 'status', 'paid_date']
