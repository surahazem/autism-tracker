from django.contrib.auth import authenticate, login
from django.db import transaction
from .models import (
    Parent, User, Session, TreatmentPlan, Child, Form, Question, Answer,
    Therapist, Diagnosis
)
from django.db.models import Q
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


def therapist_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, "You do not have a therapist profile.")
        return redirect('core:index')

    # Get therapist's data
    managed_plans = therapist.managed_plans.all()
    children = Child.objects.filter(treatment_plans__therapist=therapist).distinct()
    sessions = Session.objects.filter(treatment_plan__therapist=therapist)
    
  
    context = {
        'therapist': therapist,
        'managed_plans_count': managed_plans.count(),
        'children_count': children.count(),
        'upcoming_sessions_count': sessions.filter(status='scheduled').count(),
        'completed_sessions_count': sessions.filter(status='completed').count(),
        'recent_children': children.order_by('-created_at')[:5],
        'upcoming_sessions': sessions.filter(status='scheduled').order_by('date')[:5],
    }
    
    return render(request, 'therapist/dashboard.html', context)

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


def therapist_add_session_view(request, child_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    child = get_object_or_404(Child, id=child_id)
    active_plan = child.treatment_plans.filter(therapist=therapist, status='active').first()
    
    if not active_plan:
        messages.error(request, 'No active plan found for this child. Please create a plan first.')
        return redirect('core:therapist_children')

    if request.method == 'POST':
        # Logic to create a new session
        date = request.POST.get('date')
        time = request.POST.get('time')
        notes = request.POST.get('notes', '')
        
        # Combine date and time
        from django.utils.dateparse import parse_datetime
        dt_str = f"{date} {time}"
        
        Session.objects.create(
            treatment_plan=active_plan,
            date=dt_str,
            notes=notes,
            status='scheduled'
        )
        messages.success(request, f'New session scheduled for {child.first_name}.')
        return redirect('core:therapist_children')

    context = {
        'child': child,
        'plan': active_plan,
    }
    return render(request, 'therapist/add_session.html', context)


def therapist_sessions_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    # Status filter (default to 'scheduled')
    status = request.GET.get('status', 'scheduled')
    child_name = request.GET.get('child_name', '')

    # Base queryset: sessions for plans managed by this therapist
    sessions_qs = Session.objects.filter(treatment_plan__therapist=therapist)

    # Filter by status if not 'all'
    if status and status != 'all':
        sessions_qs = sessions_qs.filter(status=status)
    
    # Filter by child name (text search)
    if child_name:
        sessions_qs = sessions_qs.filter(
            Q(treatment_plan__child__first_name__icontains=child_name) |
            Q(treatment_plan__child__last_name__icontains=child_name)
        )

    sessions = sessions_qs.order_by('date')

    context = {
        'sessions': sessions,
        'selected_status': status,
        'child_name': child_name,
        'therapist': therapist,
    }
    
    return render(request, 'therapist/sessions.html', context)

def therapist_cancel_session_view(request, session_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    session = get_object_or_404(Session, id=session_id, treatment_plan__therapist=therapist)
    
    if session.status == 'scheduled':
        session.status = 'cancelled'
        session.save()
        messages.success(request, f'Session for {session.treatment_plan.child.first_name} has been cancelled.')
    else:
        messages.error(request, 'Only scheduled sessions can be cancelled.')
    
    return redirect('core:therapist_sessions')

def therapist_submit_session_view(request, session_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    session = get_object_or_404(Session, id=session_id, treatment_plan__therapist=therapist)
    
    if request.method == 'POST':
        # 1. Update session notes and mark completed
        notes = request.POST.get('notes', '')
        session.notes = notes
        session.status = 'completed'
        session.save()
        
        # 2. Upsert single Diagnosis (one per plan)
        diagnosis_status = request.POST.get('diagnosis_status', '').strip()
        diagnosis_description = request.POST.get('diagnosis_description', '').strip()
        if diagnosis_status or diagnosis_description:
            diagnosis = session.treatment_plan.diagnoses.first()
            if diagnosis:
                diagnosis.status = diagnosis_status or diagnosis.status
                diagnosis.description = diagnosis_description or diagnosis.description
                diagnosis.save()
            else:
                Diagnosis.objects.create(
                    treatment_plan=session.treatment_plan,
                    status=diagnosis_status or 'Observation',
                    description=diagnosis_description or ''
                )

        messages.success(request, f'Session for {session.treatment_plan.child.first_name} completed.')
        return redirect('core:therapist_sessions')

    # Load existing diagnosis for pre-fill
    existing_diagnosis = session.treatment_plan.diagnoses.first()

    context = {
        'session': session,
        'therapist': therapist,
        'existing_diagnosis': existing_diagnosis,
        'child_name': session.treatment_plan.child.first_name,
    }
    return render(request, 'therapist/submit_session.html', context)

