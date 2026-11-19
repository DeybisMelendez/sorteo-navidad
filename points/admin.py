from django.contrib import admin

from .models import Participant, PointEntry, Prize


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_points', 'prizes_won_count', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    ordering = ['name']

    def total_points(self, obj):
        """Total de puntos acumulados por el participante."""
        return obj.total_points
    total_points.short_description = "Puntos"

    def prizes_won_count(self, obj):
        """Cantidad de premios del top 5 que ganó."""
        return obj.prizes_won.count()
    prizes_won_count.short_description = "Premios"


@admin.register(PointEntry)
class PointEntryAdmin(admin.ModelAdmin):
    list_display = ('participant', 'points', 'note', 'created_at')
    list_filter = ('participant', 'created_at')
    search_fields = ('participant__name', 'note')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['participant']
    date_hierarchy = 'created_at'
    ordering = ['-created_at', '-id']


@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ('position', 'name', 'winner', 'claimed', 'created_at')
    list_filter = ('claimed', 'position')
    search_fields = ('name', 'description', 'winner__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['winner']
    ordering = ['position']

    def has_add_permission(self, request):
        """Los puestos se administran desde la aplicación (1 a 5)."""
        return False

    def has_delete_permission(self, request, obj=None):
        return False
