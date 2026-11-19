from django import forms

from .models import Participant, PointEntry, Prize


class ParticipantForm(forms.ModelForm):
    """Formulario para registrar a un participante."""

    class Meta:
        model = Participant
        fields = ['name', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nombre del jugador'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Notas opcionales'}),
        }


class PointsStepperWidget(forms.NumberInput):
    """Campo numérico con botones −/+ para anotar sin escribir (uso en celular)."""

    template_name = 'points/widgets/points_stepper.html'


class PointsField(forms.IntegerField):
    """Horas jugadas: números enteros entre 1 y 24.

    El campo del modelo es `PositiveSmallIntegerField`, que fuerza un mínimo
    de 0; aquí se declara explícitamente el rango real de 1 a 24 horas.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('min_value', 1)
        kwargs.setdefault('max_value', 24)
        super().__init__(**kwargs)


class PointEntryForm(forms.ModelForm):
    """Formulario para anotar los puntos jugados (1 punto por hora)."""

    points = PointsField(
        label='Puntos (horas jugadas)',
        help_text='Cada hora jugada equivale a 1 punto.',
        widget=PointsStepperWidget(attrs={'step': 1, 'inputmode': 'numeric'}),
    )

    class Meta:
        model = PointEntry
        fields = ['participant', 'points', 'note']
        widgets = {
            'participant': forms.Select(),
            'note': forms.TextInput(attrs={'placeholder': 'Ej: 2 horas el sábado por la tarde'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['participant'].queryset = Participant.objects.order_by('name')
        self.fields['participant'].empty_label = 'Selecciona un participante'


class PrizeForm(forms.ModelForm):
    """Formulario para configurar el premio de un puesto del top 5."""

    class Meta:
        model = Prize
        fields = ['name', 'description', 'image', 'winner', 'claimed']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: Control de consola'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción del premio'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'winner': forms.Select(),
            'claimed': forms.CheckboxInput(),
        }
        labels = {
            'winner': 'Ganador',
            'claimed': 'Premio ya reclamado',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['winner'].queryset = Participant.objects.order_by('name')
        self.fields['winner'].empty_label = 'Todavía sin ganador'
        self.fields['claimed'].help_text = 'Marca cuando el ganador recoja su premio.'
