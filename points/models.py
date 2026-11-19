from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum

# Valor por defecto si el proyecto no define PRIZE_SLOTS en settings.py.
DEFAULT_PRIZE_SLOTS = 5


def prize_slot_count():
    """Cantidad de premios del top N (configurable en settings.PRIZE_SLOTS)."""
    return int(getattr(settings, 'PRIZE_SLOTS', DEFAULT_PRIZE_SLOTS))


def validate_prize_position(value):
    """El puesto debe estar dentro del rango de premios configurado."""
    max_slots = prize_slot_count()
    if value < 1 or value > max_slots:
        raise ValidationError(
            'El puesto debe estar entre 1 y %(max_slots)s.',
            params={'max_slots': max_slots},
        )


class Participant(models.Model):
    """Persona que acumula puntos jugando en la Sala de Videojuegos Deybis."""

    name = models.CharField(max_length=100, verbose_name='Nombre')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')

    class Meta:
        ordering = ['name']
        verbose_name = 'Participante'
        verbose_name_plural = 'Participantes'

    def __str__(self):
        return self.name

    @property
    def total_points(self):
        """Puntos acumulados por el participante (1 punto por hora jugada)."""
        total = self.point_entries.aggregate(total=Sum('points'))['total']
        return total or 0


class PointEntry(models.Model):
    """Registro de puntos jugados por un participante (1 punto por hora)."""

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='point_entries',
        verbose_name='Participante',
    )
    points = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        verbose_name='Puntos (horas jugadas)',
    )
    note = models.CharField(max_length=200, blank=True, verbose_name='Nota')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Anotado el')

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Registro de puntos'
        verbose_name_plural = 'Registros de puntos'

    def __str__(self):
        return f"{self.participant.name}: +{self.points} punto(s)"


class Prize(models.Model):
    """Premio del top N que se entrega el 25 de diciembre."""

    position = models.PositiveSmallIntegerField(
        unique=True,
        validators=[validate_prize_position],
        verbose_name='Puesto',
    )
    name = models.CharField(max_length=100, verbose_name='Nombre')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    image = models.ImageField(upload_to='prizes/', blank=True, null=True, verbose_name='Imagen')
    winner = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prizes_won',
        verbose_name='Ganador',
    )
    claimed = models.BooleanField(default=False, verbose_name='Reclamado')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')

    class Meta:
        ordering = ['position']
        verbose_name = 'Premio'
        verbose_name_plural = 'Premios'

    def __str__(self):
        return f"{self.position}º lugar - {self.name}"
