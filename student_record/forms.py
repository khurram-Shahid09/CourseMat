from datetime import date

from django import forms
from .models import Student, Course, Enrollment, Teacher, Lesson, LessonImage, Batch
from django.core.exceptions import ValidationError
from .models import Enrollment
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth.models import User

class StudentForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'YYYY-MM-DD'
            },
            format='%Y-%m-%d'
        ),
        input_formats=['%Y-%m-%d']
    )

    class Meta:
        model = Student
        fields = ['name', 'age', 'email', 'phone_number', 'date_of_birth']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'date_of_birth':  # already set class for DOB
                field.widget.attrs.update({'class': 'form-control'})


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'duration', 'level']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})



class EnrollmentForm(forms.ModelForm):
    fee_at_enrollment = forms.IntegerField(
        label="Batch Fee",
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    paid_amount = forms.IntegerField(
        label="Paid Amount",
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        initial=0
    )
    fee_type = forms.ChoiceField(
        label="Fee Type",
        choices=Enrollment.FEE_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Enrollment
        fields = ['student', 'batch', 'status', 'fee_type', 'fee_at_enrollment', 'paid_amount']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        today = date.today()

        self.fields['batch'].queryset = Batch.objects.filter(
            end_date__gte=today
        ).select_related('teacher', 'course').order_by('course', 'number')

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        # Students cannot edit fee_at_enrollment, paid_amount, or fee_type
        if self.user and getattr(self.user.profile, 'role', None) == 'student':
            self.fields['fee_at_enrollment'].widget.attrs['readonly'] = True
            self.fields['paid_amount'].widget.attrs['readonly'] = True
            self.fields['fee_type'].widget.attrs['disabled'] = True

        # Set initial fee if batch is pre-selected
        batch_id = self.data.get('batch') or (self.instance.batch.id if self.instance.pk and self.instance.batch else None)
        if batch_id:
            try:
                batch = Batch.objects.get(pk=int(batch_id))
                self.fields['fee_at_enrollment'].initial = batch.fee
            except (ValueError, Batch.DoesNotExist):
                pass

    def save(self, commit=True):
        enrollment = super().save(commit=False)
        if enrollment.batch:
            # Ensure fee_at_enrollment is correct
            enrollment.fee_at_enrollment = enrollment.batch.fee

        else:
         enrollment.pending_amount = enrollment.fee_at_enrollment - (enrollment.paid_amount or 0)

        if commit:
            enrollment.save()
            self.save_m2m()
        return enrollment

class EnrollmentFeeForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['fee_type', 'fee_at_enrollment', 'paid_amount']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['name', 'email', 'phone', 'specialization', 'courses']
        widgets = {
            'courses': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'courses':
                field.widget.attrs.update({'class': 'form-control'})

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['course', 'teacher', 'start_date', 'end_date', 'fee']  # remove number field

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ['start_date', 'end_date']:
                field.widget.attrs.update({
                    'class': 'form-control',
                    'type': 'date'
                })
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        course = cleaned_data.get('course')

        if start and end and start >= end:
            raise ValidationError("Start date must be before end date.")

        # check active batches for this course
        if course:
            today = timezone.now().date()
            active_batches = Batch.objects.filter(course=course, end_date__gte=today)
            if self.instance.pk:
                active_batches = active_batches.exclude(pk=self.instance.pk)

            if active_batches.count() >= 3:
                raise ValidationError(f"Course {course.title} already has 3 active batches.")

    def save(self, commit=True):
        batch = super().save(commit=False)
        course = batch.course

        today = timezone.now().date()
        active_batches = Batch.objects.filter(course=course, end_date__gte=today).order_by('number')
        existing_numbers = list(active_batches.values_list('number', flat=True))

        # Assign first available number 1-3
        for num in range(1, 4):
            if num not in existing_numbers:
                batch.number = num
                break
        else:
            raise ValidationError(f"Course {course.title} already has 3 active batches.")

        if commit:
            batch.save()
        return batch


class LessonFilterForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        required=False,
        empty_label="All Courses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    batch = forms.ModelChoiceField(
        queryset=Batch.objects.all(),
        required=False,
        empty_label="All Batches",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class LessonForm(forms.ModelForm):
    batch = forms.ModelChoiceField(
        queryset=Batch.objects.none(),
        required=True,
        empty_label="Select batch",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Lesson
        fields = ['title', 'content', 'batch', 'teacher', 'students']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        role = getattr(user.profile, 'role', None) if user else None

        if role == 'admin':
            self.fields['batch'].queryset = Batch.objects.all()
            self.fields['teacher'].queryset = Teacher.objects.all()
            self.fields['students'].queryset = Student.objects.all()

        elif role == 'teacher':
            teacher = Teacher.objects.filter(user=user).first()
            if teacher:
                self.fields['batch'].queryset = Batch.objects.filter(teacher=teacher)
                self.fields['teacher'].queryset = Teacher.objects.filter(id=teacher.id)
                self.fields['teacher'].initial = teacher.id
                self.fields['teacher'].disabled = True

                enrolled_students = Student.objects.filter(enrollments__batch__teacher=teacher).distinct()
                self.fields['students'].queryset = enrolled_students

        elif role == 'student':
            student = Student.objects.filter(user=user).first()
            if student:
                enrolled_batches = Batch.objects.filter(enrollments__student=student)
                self.fields['batch'].queryset = enrolled_batches

                self.fields['students'].queryset = Student.objects.filter(id=student.id)
                self.fields['students'].initial = [student.id]
                self.fields['students'].disabled = True

        # Dynamically populate students if batch selected (for admin/teacher)
        batch_id = self.data.get('batch') or (self.instance.batch.id if self.instance.pk and self.instance.batch else None)
        if batch_id:
            try:
                batch = Batch.objects.get(pk=batch_id)
                self.fields['students'].queryset = Student.objects.filter(enrollments__batch=batch).distinct()
            except Batch.DoesNotExist:
                self.fields['students'].queryset = Student.objects.none()



    class LessonImageForm(forms.ModelForm):
     class Meta:
        model = LessonImage
        fields = ['image']

ROLE_CHOICES = (
    ('', 'All Roles'),
    ('student', 'Student'),
    ('teacher', 'Teacher'),
    ('admin', 'Admin'),
)


class UserFilterForm(forms.Form):
    name_or_email = forms.CharField(required=False, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Search by name/email'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=False, widget=forms.Select(attrs={'class':'form-control'}))


class UserRoleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = []  # We'll update role through related Profile model

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    def save(self, commit=True):
        role = self.cleaned_data.get('role')
        self.instance.profile.role = role
        if commit:
            self.instance.profile.save()
        return self.instance
