from django.db import models
from django.contrib.auth.models import User

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=30)
    age = models.PositiveIntegerField()
    email = models.EmailField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    roll_number = models.CharField(max_length=10, unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.roll_number:
            last_student = Student.objects.order_by('id').last()
            number = 1 if not last_student else last_student.id + 1
            self.roll_number = f"STU-{number:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.roll_number} - {self.name}"



class Course(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=600)
    fees = models.PositiveBigIntegerField()
    duration = models.PositiveIntegerField(help_text="Duration in weeks", default=3)
    level = models.CharField(
        max_length=20,
        choices=[('beginner','Beginner'), ('intermediate','Intermediate'), ('advanced','Advanced')],
        default='beginner'
    )
    course_code = models.CharField(max_length=10, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.course_code:
            last_course = Course.objects.order_by('id').last()
            number = 1 if not last_course else last_course.id + 1
            self.course_code = f"CRS-{number:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.course_code})"


    def __str__(self):
        return self.title

from django.core.exceptions import ValidationError

class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_on = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('enrolled','Enrolled'), ('completed','Completed'), ('dropped','Dropped')], default='enrolled')
    start_date = models.DateField(blank=True, null=True, default=None)
    fee_at_enrollment = models.PositiveBigIntegerField(blank=True, null=True)
    roll_number = models.CharField(max_length=20, blank=True, editable=False, unique=True)

    def clean(self):
        if self.student:
            enrollment_count = Enrollment.objects.filter(student=self.student).exclude(pk=self.pk).count()
            if enrollment_count >= 3:
                raise ValidationError(f"{self.student.name} is already enrolled in 3 courses.")

            already_enrolled = Enrollment.objects.filter(student=self.student, course=self.course).exclude(pk=self.pk).exists()
            if already_enrolled:
                raise ValidationError(
                    f"⚠️ {self.student.name} is already enrolled in the course '{self.course.title}'."
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.fee_at_enrollment is None and self.course:
            self.fee_at_enrollment = self.course.fees

        if not self.roll_number and self.course:
            last_enrollment = (
                Enrollment.objects
                .filter(course=self.course)
                .order_by('-roll_number')
                .first()
            )

            if last_enrollment:
                try:
                    last_num = int(last_enrollment.roll_number.split('-')[-1])
                except ValueError:
                    last_num = 0
                next_num = str(last_num + 1).zfill(4)
            else:
                next_num = '0001'

            self.roll_number = f"{self.course.course_code}-{next_num}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.roll_number} - {self.student.name} enrolled in {self.course.title}"
    
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile',null=True,blank=True)
    name = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True, null=True)
    teacher_code = models.CharField(max_length=10, unique=True, blank=True, editable=False)
    courses = models.ManyToManyField('Course', related_name='teachers', blank=True)

    def save(self, *args, **kwargs):
        if not self.teacher_code:
            last_teacher = Teacher.objects.order_by('id').last()
            number = 1 if not last_teacher else last_teacher.id + 1
            self.teacher_code = f"TEA-{number:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher_code} - {self.name}"
    

class Lesson(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE,blank=True, null=True)
    course = models.ForeignKey('Course', on_delete=models.CASCADE, blank=True, null=True)
    students = models.ManyToManyField('Student', blank=True)  # optional specific students
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title



class Profile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    full_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

