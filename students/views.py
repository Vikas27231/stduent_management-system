from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, get_user
from .student_utils import StudentManager
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from django.contrib import messages

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")

    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'password1', 'password2')

student_manager = StudentManager()

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created successfully! Welcome to your dashboard.')
            return redirect('dashboard')
        else:
            messages.error(request, 'There was an error with your signup. Please correct the form.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def dashboard(request):
    total_courses = len(student_manager.get_all_courses())
    total_students = len(student_manager.get_all_students(user=request.user))
    return render(request, 'dashboard.html', {
        'total_courses': total_courses,
        'total_students': total_students
    })

@login_required
def student_list(request):
    students = student_manager.get_all_students(user=request.user)
    return render(request, 'student_list.html', {'students': students})

@login_required
def student_detail(request, student_id):
    student = student_manager.get_student(student_id, user=request.user)
    if not student:
        return render(request, 'student_detail.html', {'error': 'Student not found or access denied'})
    return render(request, 'student_detail.html', {'student': student})

@login_required
def student_update(request, student_id):
    if request.method == 'POST':
        updated_data = request.POST
        profile_picture = request.FILES.get('profile_picture')
        if student_manager.update_student(student_id, updated_data, profile_picture, user=request.user):
            return redirect('manage_students')
        else:
            return render(request, 'student_form.html', {'action': 'Update', 'error': 'Failed to update student or access denied'})
    student = student_manager.get_student(student_id, user=request.user)
    if not student:
        return render(request, 'student_form.html', {'error': 'Student not found or access denied'})
    return render(request, 'student_form.html', {'student': student, 'action': 'Update'})

@login_required
def student_delete(request, student_id):
    if request.method == 'POST':
        if student_manager.delete_student(student_id, user=request.user):
            return redirect('manage_students')
    student = student_manager.get_student(student_id, user=request.user)
    if not student:
        return render(request, 'student_detail.html', {'error': 'Student not found or access denied'})
    return render(request, 'student_detail.html', {'student': student})

@login_required
def manage_students(request):
    students = student_manager.get_all_students(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            student_data = request.POST
            profile_picture = request.FILES.get('profile_picture')
            if student_manager.add_student(student_data, profile_picture, user=request.user):
                return redirect('manage_students')
        elif action == 'delete':
            student_id = request.POST.get('student_id')
            if student_id:
                student_manager.delete_student(student_id, user=request.user)
                return redirect('manage_students')
    return render(request, 'manage_students.html', {'students': students})

@login_required
def courses(request):
    courses = student_manager.get_all_courses()
    return render(request, 'courses.html', {'courses': courses})

@login_required
def manage_courses(request):
    courses = student_manager.get_all_courses()
    if request.method == 'POST':
        if 'add' in request.POST:
            course_name = request.POST.get('course_name')
            duration = request.POST.get('duration')
            if course_name and duration:
                success = student_manager.add_course({'name': course_name, 'duration': duration})
                if success:
                    return redirect('manage_courses')
                else:
                    return render(request, 'manage_courses.html', {
                        'courses': courses,
                        'error': f"Course '{course_name}' already exists. Please choose a different name."
                    })
        elif 'update' in request.POST:
            course_id = request.POST.get('course_id')
            new_name = request.POST.get('new_name')
            new_duration = request.POST.get('new_duration')
            if course_id and new_name and new_duration:
                success = student_manager.update_course(course_id, {'name': new_name, 'duration': new_duration})
                if success:
                    return redirect('manage_courses')
                else:
                    return render(request, 'manage_courses.html', {
                        'courses': courses,
                        'error': "Failed to update course. Please try again."
                    })
    return render(request, 'manage_courses.html', {'courses': courses})

@login_required
def student_report(request):
    students = student_manager.get_all_students(user=request.user)
    return render(request, 'student_report.html', {'students': students})

@login_required
def profile(request):
    user = request.user
    return render(request, 'profile.html', {'user': user})