from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


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

class Batch(models.Model):
    course = models.ForeignKey(Course, related_name="batches", on_delete=models.CASCADE)
    teacher = models.ForeignKey("Teacher", related_name="batches", on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()  # 1, 2, or 3
    start_date = models.DateField()
    end_date = models.DateField()
    fee = models.PositiveBigIntegerField()
    batch_code = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "number")  # prevent duplicate batch numbers per course

    def clean(self):
        if self.course.batches.exclude(pk=self.pk).count() >= 3:
            raise ValidationError(f"Course {self.course.title} already has 3 batches.")
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

    def save(self, *args, **kwargs):
        if not self.batch_code and self.course:
            self.batch_code = f"{self.course.course_code}-B{self.number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.batch_code} - {self.course.title} ({self.teacher.name})"




class Enrollment(models.Model):
    FEE_TYPE_CHOICES = [
        ('one_time', 'One-time'),
        ('installment', 'Installment'),
        ('custom', 'Custom'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='enrollments')
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name='enrollments')
    enrolled_on = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('enrolled', 'Enrolled'), ('completed', 'Completed'), ('dropped', 'Dropped')],
        default='enrolled'
    )
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='one_time')
    fee_at_enrollment = models.PositiveBigIntegerField(blank=True, null=True)
    paid_amount = models.PositiveBigIntegerField(default=0)  # for one-time/custom
    roll_number = models.CharField(max_length=20, blank=True, editable=False, unique=True)

    class Meta:
        unique_together = ('student', 'batch')

    def clean(self):
        if self.student:
            # Max 3 courses per student
            enrolled_courses = Enrollment.objects.filter(student=self.student).exclude(pk=self.pk).values_list(
                "batch__course", flat=True
            ).distinct()
            if len(enrolled_courses) >= 3:
                raise ValidationError(f"{self.student.name} is already enrolled in 3 courses.")

            # Prevent duplicate enrollment in same course
            if Enrollment.objects.filter(student=self.student, batch__course=self.batch.course).exclude(pk=self.pk).exists():
                raise ValidationError(f"{self.student.name} is already enrolled in {self.batch.course.title}.")

            # Enforce batch capacity (10 students max)
            if self.batch.enrollments.exclude(pk=self.pk).count() >= 10:
                raise ValidationError(f"Batch {self.batch.number} of {self.batch.course.title} is already full.")

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.fee_at_enrollment is None and self.batch:
            self.fee_at_enrollment = self.batch.fee

        if not self.roll_number:
            last_enrollment = Enrollment.objects.filter(batch=self.batch).order_by('-roll_number').first()
            last_num = 0
            if last_enrollment:
                try:
                    last_num = int(last_enrollment.roll_number.split('-')[-1])
                except ValueError:
                    pass
            next_num = str(last_num + 1).zfill(4)
            self.roll_number = f"{self.batch.course.course_code}-B{self.batch.number}-{next_num}"

        super().save(*args, **kwargs)

        # Auto-create installments if fee_type is 'installment'
        if self.fee_type == 'installment' and not self.installments.exists():
            num_months = 3
            installment_amount = self.fee_at_enrollment // num_months
            for i in range(num_months):
                due_date = self.batch.start_date + relativedelta(months=i)
                Installment.objects.create(
                    enrollment=self,
                    due_date=due_date,
                    amount=installment_amount,
                    paid_amount=0,
                    status='pending'
                )

    @property
    def pending_amount(self):
        #if self.fee_type == 'installment':
            # installments = self.installments.all()
            # if installments.exists():
            #     return sum(inst.amount - inst.paid_amount for inst in installments)
            # fallback if installments not yet created
            return max(self.fee_at_enrollment - self.paid_amount, 0)
       # return max(self.fee_at_enrollment - self.paid_amount, 0)

    @property
    def is_fully_paid(self):
        if self.fee_type == 'installment':
            return all(inst.status == 'paid' for inst in self.installments.all())
        return self.paid_amount >= self.fee_at_enrollment

    def __str__(self):
        return f"{self.roll_number} - {self.student.name} in {self.batch.course.title} (Batch {self.batch.number})"


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile',null=True,blank=True)
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
    teacher = models.ForeignKey('Teacher', on_delete=models.SET_NULL, blank=True, null=True)
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, blank=True, null=True)
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name='lessons')
    students = models.ManyToManyField('Student', blank=True, related_name='completed_lessons')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.batch.batch_code})"


class LessonImage(models.Model):
    lesson = models.ForeignKey(Lesson, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="lesson_images/")

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
#
# class Installment(models.Model):
#     enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="installments")
#     due_date = models.DateField()
#     amount = models.PositiveBigIntegerField()
#     paid_amount = models.PositiveBigIntegerField(default=0)
#     status = models.CharField(max_length=20, choices=[('pending','Pending'), ('paid','Paid')])
