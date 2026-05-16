from django.contrib.auth import authenticate, login
from django.db import transaction
from .models import (
    Parent, User, Session, TreatmentPlan, Child, Form, Answer,
    Therapist
)
from django.contrib import messages
from .serializers import RegistrationSerializer
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from .serializers import ParentProfileSerializer, TherapistProfileSerializer
from django.utils.translation import gettext as _



def index_view(request):
    return render(request, 'index.html')


def register_parent_view(request):
    if request.method == 'GET':
        return render(request, 'auth/register.html')

    data = request.POST.copy()
    if 'username' not in data or not data.get('username'):
        data['username'] = data.get('email', '')

    serializer = RegistrationSerializer(data=data)
    if not serializer.is_valid():
        return render(request, 'auth/register.html', {'errors': serializer.errors, 'data': request.POST})

    try:
        create_parent_account(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data.get("first_name", ""),
            last_name=serializer.validated_data.get("last_name", ""),
            phone_number=serializer.validated_data.get("phone"),
            address=request.POST.get("address", ""),
        )
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, 'auth/register.html', {'data': request.POST})

    messages.success(request, 'Account created successfully. Please login.')
    return redirect("core:login")

@transaction.atomic
def create_parent_account(
    *,
    username: str,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    address: str,
):
    if User.objects.filter(email=email).exists():
        raise ValueError("Email already in use")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

    parent = Parent.objects.create(
        user=user,
        phone_number=phone_number,
        address=address,
    )

    return parent


def login_view(request):
    if request.method == 'GET':
        return render(request, 'auth/login.html')

    email = request.POST.get('email')
    password = request.POST.get('password')

    user = authenticate(request, username=email, password=password)
    if user is not None:
        login(request, user)
        return redirect('/')

    messages.error(request, 'Invalid email or password')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('core:index')


def parent_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        # In case the user is not a parent, redirect or show error
        messages.error(request, "You do not have a parent profile.")
        return redirect('core:index')

    children = parent.children.all()
    children_count = children.count()
    
    # Get all treatment plans for these children (only active ones)
    active_plans_count = TreatmentPlan.objects.filter(child__parents=parent, status='active').count()
    
    # Get sessions related to these children's plans
    sessions = Session.objects.filter(treatment_plan__child__parents=parent)
    upcoming_sessions_count = sessions.filter(status='scheduled').count()
    completed_sessions_count = sessions.filter(status='completed').count()
    
    context = {
        'children': children.order_by('-created_at')[:3],
        'upcoming_sessions': sessions.filter(status='scheduled').order_by('date')[:3],
        'children_count': children_count,
        'active_plans_count': active_plans_count,
        'upcoming_sessions_count': upcoming_sessions_count,
        'completed_sessions_count': completed_sessions_count,
    }
    
    return render(request, 'parent/dashboard.html', context)


def parent_profile_view(request):
    parent = request.user.parent_profile

    if request.method == "POST":

        serializer = ParentProfileSerializer(data=request.POST)

        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, error)

            return render(request, "parent/profile.html", {
                "parent": parent
            })

        data = serializer.validated_data
        user = request.user

        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.save()

        parent.phone_number = data["phone"]
        parent.address = data["address"]
        parent.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("core:parent_profile")

    return render(request, "parent/profile.html", {
        "parent": parent
    })


def therapist_profile_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, "You do not have a therapist profile.")
        return redirect('core:index')

    if request.method == "POST":
        serializer = TherapistProfileSerializer(data=request.POST)

        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

            return render(request, "therapist/profile.html", {
                "therapist": therapist
            })

        data = serializer.validated_data
        user = request.user

        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.save()

        therapist.specialization = data["specialization"]
        therapist.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("core:therapist_profile")

    return render(request, "therapist/profile.html", {
        "therapist": therapist
    })


def therapist_children_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        dob = request.POST.get('dob')
        parent_code = request.POST.get('parent_code')
        
        if not all([first_name, last_name, dob, parent_code]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                parent = Parent.objects.get(parent_shared_id=parent_code)
                with transaction.atomic():
                    child = Child.objects.create(
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=dob,
                        parents=parent
                    )
                    # Create a treatment plan immediately as per requirements
                    TreatmentPlan.objects.create(
                        therapist=therapist,
                        child=child
                    )
                messages.success(request, f'Child {child.first_name} added and assigned to you.')
                return redirect('core:therapist_children')
            except Parent.DoesNotExist:
                messages.error(request, 'Invalid parent code. No parent found with this ID.')
            except Exception as e:
                messages.error(request, f'Error adding child: {str(e)}')

    children = Child.objects.filter(treatment_plans__therapist=therapist).distinct().order_by('first_name')
    
    for child in children:
        child.current_active_plan = child.treatment_plans.filter(therapist=therapist, status='active').first()

    context = {
        'children': children,
        'therapist': therapist,
    }
    
    return render(request, 'therapist/children.html', context)

def my_children_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, "You do not have a parent profile.")
        return redirect('core:index')

    children = parent.children.all().order_by('first_name')
    
    return render(request, 'parent/children.html', {'children': children})


def assessment_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, "You do not have a parent profile.")
        return redirect('core:index')

    children = parent.children.all()
    selected_child_id = request.GET.get('child_id')
    selected_child = None
    form_obj = Form.objects.filter(title="Initial Assessment").first() or Form.objects.first()
    
    questions_with_answers = []
    has_answered = False

    if selected_child_id:
        selected_child = get_object_or_404(Child, id=selected_child_id, parents=parent)
        
        if form_obj:
            questions = form_obj.questions.all()
            answers = Answer.objects.filter(child=selected_child, question__form=form_obj)
            has_answered = answers.exists()
            
            # Create a mapping for quick lookup
            answers_map = {ans.question_id: ans.text for ans in answers}
            
            for q in questions:
                # We attach the answer to the question object dynamically
                q.existing_answer = answers_map.get(q.id, "")
                questions_with_answers.append(q)
            
            if request.method == 'POST' and not has_answered:
                with transaction.atomic():
                    for question in questions:
                        answer_text = request.POST.get(f'question_{question.id}')
                        if answer_text:
                            Answer.objects.create(
                                question=question,
                                child=selected_child,
                                text=answer_text
                            )
                messages.success(request, "Assessment submitted successfully!")
                return redirect(f"{request.path}?child_id={selected_child.id}")

    context = {
        'children': children,
        'selected_child': selected_child,
        'form': form_obj,
        'questions': questions_with_answers,
        'has_answered': has_answered,
    }
    
    return render(request, 'parent/developmental-assessment.html', context)

