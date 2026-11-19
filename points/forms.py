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


class PointEntryForm(forms.ModelForm):
    """Formulario para anotar los puntos jugados (1 punto por hora)."""

    class Meta:
        model = PointEntry
        fields = ['participant', 'points', 'note']
        widgets = {
            'participant': forms.Select(),
            'points': forms.NumberInput(attrs={'min': 1, 'max': 24, 'step': 1, 'list': 'horas-comunes'}),
            'note': forms.TextInput(attrs={'placeholder': 'Ej: 2 horas el sábado por la tarde'}),
        }
        labels = {
            'points': 'Puntos (horas jugadas)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['participant'].queryset = Participant.objects.order_by('name')
        self.fields['participant'].empty_label = 'Selecciona un participante'
        self.fields['points'].help_text = 'Cada hora jugada equivale a 1 punto.'


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
