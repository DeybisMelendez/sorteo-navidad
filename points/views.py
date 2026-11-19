from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ParticipantForm, PointEntryForm, PrizeForm
from .models import Participant, PointEntry, Prize, prize_slot_count

# Periodo de acumulación de puntos (ciclo Navidad 2026).
START_DATE = date(2026, 11, 1)
END_DATE = date(2026, 12, 24)
# Fecha de entrega de los premios del top 5.
AWARD_DATE = date(2026, 12, 25)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def get_ranking():
    """Participantes con puntos, ordenados de mayor a menor."""
    return (
        Participant.objects.annotate(points=Sum('point_entries__points'))
        .filter(points__gt=0)
        .order_by('-points', 'name')
    )


def get_ranked_list():
    """Lista de tuplas (puesto, participante) con los empates resueltos."""
    ranked = []
    previous_points = None
    current_rank = 0
    for index, participant in enumerate(get_ranking(), start=1):
        if previous_points is None or participant.points != previous_points:
            current_rank = index
            previous_points = participant.points
        ranked.append((current_rank, participant))
    return ranked


def period_is_open():
    """True mientras se puedan anotar puntos (del 1 de noviembre al 24 de diciembre)."""
    return START_DATE <= timezone.localdate() <= END_DATE


def days_until_award():
    """Días que faltan para la entrega de premios (0 si ya pasó la fecha)."""
    return max((AWARD_DATE - timezone.localdate()).days, 0)


# ---------------------------------------------------------------------------
# Vistas públicas
# ---------------------------------------------------------------------------


def home(request):
    """Portada con el top N, el estado de los premios y las fechas clave."""
    ranking = get_ranked_list()
    # Solo los premios dentro del top N configurado.
    prizes = list(
        Prize.objects.select_related('winner').filter(position__lte=prize_slot_count())
    )
    total_points = PointEntry.objects.aggregate(total=Sum('points'))['total'] or 0

    context = {
        'top_ranking': ranking[:prize_slot_count()],
        'prizes': prizes,
        'prize_count': prize_slot_count(),
        'total_points': total_points,
        'participant_count': Participant.objects.count(),
        'days_to_award': days_until_award(),
        'award_date': AWARD_DATE,
        'start_date': START_DATE,
        'end_date': END_DATE,
        'period_open': period_is_open(),
        'is_award_day': timezone.localdate() == AWARD_DATE,
    }
    return render(request, 'index.html', context)


def leaderboard(request):
    """Clasificación completa de participantes por puntos acumulados."""
    ranked = get_ranked_list()

    # Premios ya ganados por cada participante (consulta aparte para no
    # duplicar las filas de los registros de puntos).
    prizes_by_participant = {}
    for prize in Prize.objects.select_related('winner').exclude(winner=None):
        prizes_by_participant.setdefault(prize.winner_id, []).append(prize)

    context = {
        'ranked': ranked,
        'podium': ranked[:3],
        'prizes_by_participant': prizes_by_participant,
        'total_points': PointEntry.objects.aggregate(total=Sum('points'))['total'] or 0,
        'days_to_award': days_until_award(),
        'award_date': AWARD_DATE,
    }
    return render(request, 'leaderboard.html', context)


def prizes(request):
    """Los premios del top N y quién los ganó."""
    prizes = list(Prize.objects.select_related('winner'))
    by_position = {prize.position: prize for prize in prizes}
    ranked = get_ranked_list()

    # Siempre se muestran los puestos configurados, aunque el staff aún no
    # haya definido el premio de alguno de ellos.
    slots = [
        {
            'position': position,
            'prize': by_position.get(position),
            'suggested': ranked[position - 1][1] if position <= len(ranked) else None,
        }
        for position in range(1, prize_slot_count() + 1)
    ]

    context = {
        'slots': slots,
        'prize_count': prize_slot_count(),
        'award_date': AWARD_DATE,
        'days_to_award': days_until_award(),
        'is_award_day': timezone.localdate() == AWARD_DATE,
    }
    return render(request, 'prizes.html', context)


def participant_detail(request, participant_id):
    """Historial de puntos de un participante."""
    participant = get_object_or_404(
        Participant.objects.annotate(points=Sum('point_entries__points')),
        pk=participant_id,
    )
    entries = participant.point_entries.all()

    # Puesto del participante dentro de la clasificación (0 si no tiene puntos).
    rank = 0
    for position, ranked_participant in get_ranked_list():
        if ranked_participant.pk == participant.pk:
            rank = position
            break

    context = {
        'participant': participant,
        'entries': entries,
        'total_points': participant.points or 0,
        'rank': rank,
        'prizes': participant.prizes_won.all(),
    }
    return render(request, 'participant_detail.html', context)


# ---------------------------------------------------------------------------
# Vistas de administración (solo staff)
# ---------------------------------------------------------------------------


@login_required
def add_participant(request):
    """Crea un nuevo participante (solo usuarios registrados)."""
    # `next=anotar` vuelve al formulario de puntos con el jugador ya elegido.
    next_page = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save()
            messages.success(request, f"Participante '{participant.name}' agregado correctamente.")
            if next_page == 'anotar':
                return redirect(f"{reverse('add_points')}?participant={participant.pk}")
            return redirect('add_participant')
        messages.error(request, "Ocurrió un error al guardar el participante. Verifica los datos.")
    else:
        form = ParticipantForm()

    participants = Participant.objects.annotate(
        points=Sum('point_entries__points')
    ).order_by('-points', 'name')

    context = {
        'form': form,
        'participants': participants,
        'next_page': next_page,
    }
    return render(request, 'add_participant.html', context)


@login_required
def add_points(request):
    """Registra los puntos jugados por un participante (solo usuarios registrados)."""
    period_open = period_is_open()

    if request.method == 'POST':
        if not period_open:
            messages.error(request, "⛔ La acumulación de puntos ya está cerrada.")
            return redirect('add_points')
        form = PointEntryForm(request.POST)
        if form.is_valid():
            entry = form.save()
            messages.success(
                request,
                f"✨ Se anotaron {entry.points} punto(s) a {entry.participant.name}.",
            )
            return redirect('add_points')
        messages.error(request, "No se pudieron anotar los puntos. Verifica los datos.")
    else:
        form = PointEntryForm()

    # Permite preseleccionar al participante (/?participant=<id>).
    preselected = request.GET.get('participant')
    if preselected and not form.is_bound:
        form.fields['participant'].initial = preselected

    context = {
        'form': form,
        'period_open': period_open,
        'recent_entries': PointEntry.objects.select_related('participant')[:25],
        'participants': Participant.objects.annotate(
            points=Sum('point_entries__points')
        ).order_by('-points', 'name'),
    }
    return render(request, 'add_points.html', context)


@login_required
def delete_point_entry(request, entry_id):
    """Elimina un registro de puntos mal anotado (solo usuarios registrados)."""
    entry = get_object_or_404(PointEntry, pk=entry_id)

    if request.method != 'POST':
        return redirect('add_points')

    participant_name = entry.participant.name
    points = entry.points
    entry.delete()
    messages.success(request, f"🗑️ Se eliminaron {points} punto(s) de {participant_name}.")
    return redirect('add_points')


@staff_member_required
def edit_prize(request, position):
    """Configura el premio de un puesto del top N (solo staff)."""
    if position < 1 or position > prize_slot_count():
        messages.error(request, "Ese puesto no existe.")
        return redirect('prizes')

    prize, _ = Prize.objects.get_or_create(
        position=position, defaults={'name': f"Premio {position}º lugar"}
    )

    if request.method == 'POST':
        form = PrizeForm(request.POST, request.FILES, instance=prize)
        if form.is_valid():
            form.save()
            messages.success(request, f"🎁 Premio del {position}º lugar actualizado correctamente.")
            return redirect('prizes')
        messages.error(request, "No se pudo guardar el premio. Verifica los datos.")
    else:
        form = PrizeForm(instance=prize)

    context = {
        'form': form,
        'position': position,
        'prize': prize,
    }
    return render(request, 'prize_form.html', context)


@staff_member_required
def assign_top_prizes(request):
    """Asigna los ganadores del top 5 a los premios configurados."""
    if request.method != 'POST':
        return redirect('prizes')

    ranked = get_ranked_list()[:prize_slot_count()]
    assigned, missing = [], []

    with transaction.atomic():
        for position, (_, participant) in enumerate(ranked, start=1):
            prize = Prize.objects.filter(position=position).first()
            if prize is None:
                missing.append(position)
                continue
            prize.winner = participant
            prize.save(update_fields=['winner'])
            assigned.append(f"{position}º lugar: {participant.name}")

    if assigned:
        messages.success(request, "🏆 Top 5 asignado: " + " | ".join(assigned))
    if missing:
        messages.warning(
            request,
            f"Configura primero los premios de los puestos: {', '.join(f'{p}º' for p in missing)}.",
        )
    if not ranked:
        messages.warning(request, "Todavía no hay participantes con puntos para premiar.")

    return redirect('prizes')


@staff_member_required
def claim_prize(request, prize_id):
    """Marca un premio como reclamado por su ganador."""
    prize = get_object_or_404(Prize, pk=prize_id)

    if request.method != 'POST':
        return redirect('prizes')

    if prize.claimed:
        messages.warning(request, f"⚠️ El premio de {prize.name} ya fue reclamado anteriormente.")
    else:
        prize.claimed = True
        prize.save(update_fields=['claimed'])
        messages.success(request, f"🏆 Has marcado como reclamado el premio de {prize.name}.")

    return redirect('prizes')
