from django import forms
from .models import Student, Course, Enrollment, Teacher, Lesson, LessonImage
from django.core.exceptions import ValidationError
from .models import Enrollment
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
        fields = ['title', 'description', 'fees', 'duration', 'level']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})



class EnrollmentForm(forms.ModelForm):
    fee_at_enrollment = forms.IntegerField(
        label="Course Fee",
        required=True,  
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date'
            }
        )
    )

    class Meta:
        model = Enrollment
        fields = ['student', 'course', 'start_date', 'status', 'fee_at_enrollment']



    def save(self, commit=True):
        enrollment = super().save(commit=False)
        enrollment.fee_at_enrollment = self.cleaned_data.get('fee_at_enrollment')
        if commit:
            enrollment.save()
            self.save_m2m()
        return enrollment
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




class LessonFilterForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        required=False,
        empty_label="All Courses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class LessonForm(forms.ModelForm):
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=True,
        empty_label="Select course",
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
        fields = ['title', 'content', 'course', 'teacher', 'students']

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.profile.role == 'teacher' and teacher:
            self.fields['course'].queryset = teacher.courses.all()
            self.fields['teacher'].queryset = Teacher.objects.filter(id=teacher.id)
            self.fields['teacher'].initial = teacher.id
            self.fields['teacher'].disabled = True
        else:
            self.fields['course'].queryset = Course.objects.all()
            self.fields['teacher'].queryset = Teacher.objects.all()


    class LessonImageForm(forms.ModelForm):
     class Meta:
        model = LessonImage
        fields = ['image']



