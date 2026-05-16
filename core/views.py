from django.contrib.auth import authenticate, login
from django.db import transaction
from .models import (
    Parent, User, Session, TreatmentPlan, Child, Form, Question, Answer,
    Therapist, Goal, Treatment, Diagnosis, DrawingImage,
    Indicator, TreatmentPlanIndicator, ProgressRecord
)
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from .serializers import RegistrationSerializer
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from .serializers import ParentProfileSerializer, TherapistProfileSerializer
import os
import base64
from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile
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





def therapist_treatment_plans_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    # Filters
    status = request.GET.get('status', 'active')
    child_name = request.GET.get('child_name', '')

    # Base queryset
    plans_qs = TreatmentPlan.objects.filter(therapist=therapist)

    # Filter by status if not 'all'
    if status and status != 'all':
        plans_qs = plans_qs.filter(status=status)
    
    # Filter by child name (text search)
    if child_name:
        plans_qs = plans_qs.filter(
            Q(child__first_name__icontains=child_name) |
            Q(child__last_name__icontains=child_name)
        )

    plans = plans_qs.select_related('child').order_by('-created_at')
    
    # Get children assigned to this therapist for the "Add New Plan" modal
    assigned_children = Child.objects.filter(treatment_plans__therapist=therapist).distinct().order_by('first_name')

    context = {
        'plans': plans,
        'selected_status': status,
        'child_name': child_name,
        'therapist': therapist,
        'assigned_children': assigned_children,
    }
    
    return render(request, 'therapist/treatment-plans.html', context)


def therapist_treatment_plan_detail_view(request, plan_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    plan = get_object_or_404(TreatmentPlan, id=plan_id, therapist=therapist)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_goal':
            goal_desc = request.POST.get('goal_description', '').strip()
            if goal_desc:
                Goal.objects.create(treatment_plan=plan, target_description=goal_desc)
                messages.success(request, 'Goal added.')

        elif action == 'add_treatment':
            t_type = request.POST.get('treatment_type', '').strip()
            t_desc = request.POST.get('treatment_description', '').strip()
            if t_type or t_desc:
                Treatment.objects.create(
                    treatment_plan=plan,
                    type=t_type or 'General',
                    description=t_desc
                )
                messages.success(request, 'Treatment method added.')

        elif action == 'add_indicator':
            ind_id = request.POST.get('indicator_id', '').strip()
            ind_desc = request.POST.get('indicator_description', '').strip()
            if ind_id:
                try:
                    indicator = Indicator.objects.get(id=int(ind_id))
                    tpi, created = TreatmentPlanIndicator.objects.get_or_create(
                        treatment_plan=plan,
                        indicator=indicator,
                        defaults={'description': ind_desc}
                    )
                    if not created:
                        tpi.description = ind_desc
                        tpi.save(update_fields=['description'])
                    messages.success(request, f'Indicator "{indicator.metric_name}" linked.')
                except (Indicator.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid indicator selected.')

        elif action == 'update_diagnosis':
            d_status = request.POST.get('diagnosis_status', '').strip()
            d_desc = request.POST.get('diagnosis_description', '').strip()
            if d_status or d_desc:
                diagnosis = plan.diagnoses.first()
                if diagnosis:
                    diagnosis.status = d_status or diagnosis.status
                    diagnosis.description = d_desc or diagnosis.description
                    diagnosis.save()
                else:
                    Diagnosis.objects.create(
                        treatment_plan=plan,
                        status=d_status or 'Observation',
                        description=d_desc
                    )
                messages.success(request, 'Diagnosis updated.')

        elif action == 'delete_goal':
            goal_id = request.POST.get('goal_id')
            Goal.objects.filter(id=goal_id, treatment_plan=plan).delete()

        elif action == 'delete_treatment':
            treatment_id = request.POST.get('treatment_id')
            Treatment.objects.filter(id=treatment_id, treatment_plan=plan).delete()

        elif action == 'delete_indicator':
            tpi_id = request.POST.get('tpi_id')
            TreatmentPlanIndicator.objects.filter(id=tpi_id, treatment_plan=plan).delete()

        return redirect('core:therapist_treatment_plan_detail', plan_id=plan.id)

    all_indicators = Indicator.objects.all().order_by('metric_name')
    linked_indicator_ids = plan.plan_indicators.values_list('indicator_id', flat=True)
    diagnosis = plan.diagnoses.first()

    context = {
        'plan': plan,
        'sessions': plan.sessions.all().order_by('-date'),
        'diagnosis': diagnosis,
        'goals': plan.goals.all().order_by('-created_at'),
        'treatments': plan.treatments.all().order_by('-created_at'),
        'plan_indicators': plan.plan_indicators.select_related('indicator').prefetch_related('progress_records').all(),
        'all_indicators': all_indicators,
        'linked_indicator_ids': linked_indicator_ids,
        'therapist': therapist,
    }
    return render(request, 'therapist/treatment-plan-detail.html', context)


def therapist_complete_plan_view(request, plan_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    plan = get_object_or_404(TreatmentPlan, id=plan_id, therapist=therapist)
    
    if plan.status != 'completed':
        plan.status = 'completed'
        plan.save()
        messages.success(request, f'Treatment plan for {plan.child.first_name} has been marked as completed.')
    else:
        messages.warning(request, 'Plan is already completed.')
    
    return redirect('core:therapist_treatment_plan_detail', plan_id=plan.id)


def therapist_add_plan_view(request, child_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        # Logic to create a new treatment plan
        TreatmentPlan.objects.create(
            therapist=therapist,
            child=child,
            status='active'
        )
        messages.success(request, f'New treatment plan created for {child.first_name}.')
        return redirect('core:therapist_children')

    context = {
        'child': child,
        'therapist': therapist,
    }
    return render(request, 'therapist/add_plan.html', context)


def treatment_plans_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, "You do not have a parent profile.")
        return redirect('core:index')

    # Get all treatment plans for these children
    treatment_plans = TreatmentPlan.objects.filter(child__parents=parent).select_related('child', 'therapist', 'therapist__user')
    
    context = {
        'treatment_plans': treatment_plans,
    }
    return render(request, 'parent/treatment-plans.html', context)



def treatment_plan_detail_view(request, plan_id):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, "You do not have a parent profile.")
        return redirect('core:index')

    plan = get_object_or_404(TreatmentPlan, id=plan_id, child__parents=parent)
    
    context = {
        'plan': plan,
    }
    return render(request, 'parent/treatment-plan-detail.html', context)




def therapist_create_plan_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    try:
        therapist = request.user.therapist_profile
    except (AttributeError, Therapist.DoesNotExist):
        messages.error(request, 'You do not have a therapist profile.')
        return redirect('core:index')

    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        if not child_id:
            messages.error(request, 'Please select a child.')
            return redirect('core:therapist_treatment_plans')
        
        child = get_object_or_404(Child, id=child_id)
        
        # Check if the child already has an active plan
        if child.treatment_plans.filter(status='active').exists():
            messages.error(request, f'{child.first_name} already has an active treatment plan.')
            return redirect('core:therapist_treatment_plans')
        
        # Create new plan
        TreatmentPlan.objects.create(
            therapist=therapist,
            child=child,
            status='active'
        )
        messages.success(request, f'New treatment plan created for {child.first_name}.')
    
    return redirect('core:therapist_treatment_plans')



def _analyze_drawing(image_path_full):
    img = Image.open(image_path_full).convert('RGB')
    width, height = img.size
    total_pixels = width * height

    BACKGROUND_THRESHOLD = 240
    pixel_array = img.load()
    
    drawn_count = 0
    warm_pixels = 0
    cool_pixels = 0
    dark_pixels = 0

    meaningful_colors = set()

    # Process every 2nd pixel for speed
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            r, g, b = pixel_array[x, y]
            if not (r > BACKGROUND_THRESHOLD and g > BACKGROUND_THRESHOLD and b > BACKGROUND_THRESHOLD):
                drawn_count += 1
                
                if drawn_count % 10 == 0 and len(meaningful_colors) < 24:
                    meaningful_colors.add((r, g, b))

                avg_brightness = (r + g + b) / 3
                if avg_brightness < 100:
                    dark_pixels += 1
                elif r > g + 20 and r > b + 20: 
                    warm_pixels += 1
                elif b > r + 20 or g > r + 20: 
                    cool_pixels += 1

    # Calculate density (divided by 4 because we skipped pixels)
    density_pct = round((drawn_count / (total_pixels / 4)) * 100, 1) 

    # Determine emotional state
    if density_pct < 2.0:
        emotional_state = 'withdrawn'
        confidence = 0.90
    elif density_pct > 40.0 and dark_pixels > (drawn_count * 0.4):
        emotional_state = 'overwhelmed'
        confidence = 0.88
    elif density_pct > 30.0 and warm_pixels > (drawn_count * 0.4):
        emotional_state = 'energetic'
        confidence = 0.85
    elif dark_pixels > (drawn_count * 0.5):
        emotional_state = 'anxious'
        confidence = 0.82
    elif warm_pixels > (drawn_count * 0.3):
        emotional_state = 'happy'
        confidence = 0.88
    else:
        emotional_state = 'calm'
        confidence = 0.80

    emotion_notes = {
        'withdrawn': _("The child covered only %(density)s%% of the canvas. This low engagement may suggest a withdrawn state.") % {'density': density_pct},
        'calm': _("The measured marks and balanced colors indicate a calm, emotionally regulated state."),
        'happy': _("Warm, bright colors reflect a joyful and happy emotional state."),
        'energetic': _("High activity detected (%(density)s%% coverage) with warm colors. This indicates high energy.") % {'density': density_pct},
        'overwhelmed': _("Heavy canvas coverage (%(density)s%%) with darker tones may indicate the child is feeling overwhelmed.") % {'density': density_pct},
        'anxious': _("A high proportion of dark or harsh tones suggests possible tension or anxious feelings."),
    }

    dominant_colors = ['#{:02X}{:02X}{:02X}'.format(*c) for c in list(meaningful_colors)[:8]]
    warm_r = round((warm_pixels / max(drawn_count, 1)) * 100, 1)
    cool_r = round((cool_pixels / max(drawn_count, 1)) * 100, 1)
    dark_r = round((dark_pixels / max(drawn_count, 1)) * 100, 1)

    return {
        'stroke_density': density_pct,
        'emotional_state': emotional_state,
        'confidence': confidence,
        'notes': emotion_notes.get(emotional_state, "Analysis complete."),
    }


def drawing_canvas_view(request, child_id):
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'You do not have a parent profile.')
        return redirect('core:index')

    child = get_object_or_404(Child, id=child_id, parents=parent)

    # Enforce one drawing per child per day
    today = timezone.localdate()
    today_drawing = child.drawings.filter(draw_date=today).first()

    if request.method == 'POST':
        if today_drawing:
            messages.warning(request, f'{child.first_name} has already drawn today. Come back tomorrow!')
            return redirect('core:drawing_results', drawing_id=today_drawing.id)

        canvas_data = request.POST.get('canvas_data', '')

        if not canvas_data or not canvas_data.startswith('data:image/png;base64,'):
            messages.error(request, 'No drawing data received. Please try again.')
            return redirect('core:drawing_canvas', child_id=child_id)

        # Decode base64 image
        header, encoded = canvas_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        image_file = ContentFile(image_bytes, name=f'drawing_{child_id}.png')

        # Save DrawingImage record
        drawing = DrawingImage.objects.create(
            child=child,
            image_path=image_file,
            draw_date=today,
        )

        # Run analysis on the saved file
        full_path = os.path.join(settings.MEDIA_ROOT, drawing.image_path.name)
        try:
            metrics = _analyze_drawing(full_path)
        except Exception as e:
            metrics = {
                'stroke_density': 0.0,
                'emotional_state': 'calm',
                'confidence': 0.5,
                'notes': 'Analysis could not be completed for this drawing.',
            }

        # Update DrawingImage with analysis results
        drawing.stroke_density = metrics['stroke_density']
        drawing.emotional_state = metrics['emotional_state']
        drawing.confidence = metrics['confidence']
        drawing.analysis_notes = metrics['notes']
        drawing.save()

      
        _apply_drawing_to_progress(child, drawing, metrics)

        return redirect('core:drawing_results', drawing_id=drawing.id)

    # GET – if already drew today, redirect to results
    if today_drawing:
        messages.info(request, f'{child.first_name} already has a drawing for today. View the results below.')
        return redirect('core:drawing_results', drawing_id=today_drawing.id)

    recent_drawings = child.drawings.order_by('-upload_date')[:5]
    context = {
        'child': child,
        'recent_drawings': recent_drawings,
    }
    return render(request, 'parent/drawing_canvas.html', context)



def drawing_results_view(request, drawing_id):
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'You do not have a parent profile.')
        return redirect('core:index')

    drawing = get_object_or_404(DrawingImage, id=drawing_id, child__parents=parent)

    context = {
        'drawing': drawing,
        'child': drawing.child,
    }
    return render(request, 'parent/drawing_results.html', context)


def drawing_reanalyze_view(request, drawing_id):
    """ Allows parent to re-run analysis for a stale drawing. """
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'You do not have a parent profile.')
        return redirect('core:index')

    drawing = get_object_or_404(DrawingImage, id=drawing_id, child__parents=parent)
    
    full_path = os.path.join(settings.MEDIA_ROOT, drawing.image_path.name)
    
    if not os.path.exists(full_path):
        messages.error(request, "Drawing image file not found on server.")
        return redirect('core:drawing_results', drawing_id=drawing.id)

    try:
        metrics = _analyze_drawing(full_path)
        
        # Update DrawingImage with new analysis results
        drawing.stroke_density = metrics['stroke_density']
        drawing.emotional_state = metrics['emotional_state']
        drawing.confidence = metrics['confidence']
        drawing.analysis_notes = metrics['notes']
        drawing.save()
        
        # Also update progress records
        _apply_drawing_to_progress(drawing.child, drawing, metrics)
        
        messages.success(request, "Drawing analysis has been updated with the latest engine.")
    except Exception as e:
        messages.error(request, f"Error during re-analysis: {str(e)}")

    return redirect('core:drawing_results', drawing_id=drawing.id)




_EMOTIONAL_SCORE_MAP = {
    'calm':        75.0,
    'happy':       80.0,
    'energetic':   65.0,
    'anxious':     40.0,
    'overwhelmed': 30.0,
    'withdrawn':   20.0,
}


def _apply_drawing_to_progress(child, drawing, metrics):
    active_plan = child.active_plan
    if not active_plan:
        return

    today = timezone.localdate()
    emotional_state = metrics.get('emotional_state', 'calm')
    drawing_score = _EMOTIONAL_SCORE_MAP.get(emotional_state, 50.0)
    confidence = metrics.get('confidence', 0.5)

    today_records = ProgressRecord.objects.filter(
        treatment_plan_indicator__treatment_plan=active_plan,
        date=today,
        is_submitted=False,
    )

    for record in today_records:
        blended = record.indicator_value * (1 - 0.4 * confidence) + drawing_score * 0.4 * confidence
        record.indicator_value = round(min(100.0, max(0.0, blended)), 2)
        record.drawing_image = drawing
        record.save(update_fields=['indicator_value', 'drawing_image'])



def parent_progress_view(request, plan_id):
    """Shows all indicators for a treatment plan."""
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'You do not have a parent profile.')
        return redirect('core:index')

    plan = get_object_or_404(TreatmentPlan, id=plan_id, child__parents=parent)
    today = timezone.localdate()

    # Ensure today's record exists for every indicator linked to this plan
    with transaction.atomic():
        for tpi in plan.plan_indicators.select_related('indicator').all():
            ProgressRecord.objects.get_or_create(
                treatment_plan_indicator=tpi,
                date=today,
                defaults={'indicator_value': 0.0},
            )

    # Fetch all indicators with their records (today first, then history)
    plan_indicators = plan.plan_indicators.select_related('indicator').prefetch_related(
        'progress_records'
    ).all().order_by('indicator__metric_name')

    indicators_data = []
    for tpi in plan_indicators:
        records = tpi.progress_records.order_by('-date')  # newest first
        today_record = records.filter(date=today).first()
        history = records.exclude(date=today)
        indicators_data.append({
            'tpi': tpi,
            'today_record': today_record,
            'history': history,
        })

    context = {
        'plan': plan,
        'child': plan.child,
        'indicators_data': indicators_data,
        'today': today,
    }
    return render(request, 'parent/progress_tracking.html', context)


def parent_progress_submit_view(request, record_id):
    """Parent submits the slider value + optional note for a single ProgressRecord."""
    if not request.user.is_authenticated:
        return redirect('core:login')

    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'You do not have a parent profile.')
        return redirect('core:index')

    record = get_object_or_404(
        ProgressRecord,
        id=record_id,
        treatment_plan_indicator__treatment_plan__child__parents=parent,
    )

    if request.method == 'POST':
        if record.is_submitted:
            messages.warning(request, "You have already submitted progress for this indicator today.")
            return redirect('core:parent_progress', plan_id=record.treatment_plan_indicator.treatment_plan_id)

        if record.date != timezone.localdate():
            messages.error(request, "You can only submit progress for the current day.")
            return redirect('core:parent_progress', plan_id=record.treatment_plan_indicator.treatment_plan_id)

        note_text = request.POST.get('notes', '').strip()
        custom_value = request.POST.get('indicator_value')

        with transaction.atomic():
            if custom_value is not None:
                try:
                    record.indicator_value = float(custom_value)
                except ValueError:
                    pass
            record.notes = note_text
            record.is_submitted = True
            record.save(update_fields=['indicator_value', 'notes', 'is_submitted'])

        ind_name = record.treatment_plan_indicator.indicator.metric_name
        messages.success(request, f'Progress for "{ind_name}" updated successfully!')
        return redirect(
            'core:parent_progress',
            plan_id=record.treatment_plan_indicator.treatment_plan_id
        )

    return redirect(
        'core:parent_progress',
        plan_id=record.treatment_plan_indicator.treatment_plan_id
    )
