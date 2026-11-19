"""Limpieza de los datos del sistema de rifas (2025) y paso a puntos.

El proyecto antes funcionaba con rifas, números y ganadores diarios. Ese
modelo ya no existe: ahora se acumulan puntos y el top 5 recibe los premios
del 25 de diciembre.

Esta migración:
  1. Conserva los participantes que ya estaban registrados.
  2. Elimina las rifas, los números y el historial de ganadores diarios.
"""

from django.db import migrations
from django.utils import timezone

LEGACY_TABLES = (
    'raffle_rafflenumber',
    'raffle_raffle',
    'raffle_dailywinner',
    'raffle_participant',
)


def copy_legacy_participants(apps, schema_editor):
    """Copia los participantes de la base anterior a la nueva tabla."""
    connection = schema_editor.connection
    table_names = set(connection.introspection.table_names())

    if 'raffle_participant' not in table_names:
        return

    with connection.cursor() as cursor:
        cursor.execute('SELECT id, name, notes, created_at FROM raffle_participant ORDER BY id')
        rows = cursor.fetchall()

    Participant = apps.get_model('points', 'Participant')
    for old_id, name, notes, created_at in rows:
        participant, _ = Participant.objects.update_or_create(
            pk=old_id,
            defaults={'name': name, 'notes': notes},
        )
        # auto_now_add ignora el valor en el INSERT, se actualiza aparte.
        if created_at is not None:
            if timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            Participant.objects.filter(pk=participant.pk).update(created_at=created_at)


def drop_legacy_tables(apps, schema_editor):
    """Elimina las tablas del sistema de rifas y sus registros de migración."""
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        for table in LEGACY_TABLES:
            cursor.execute(f'DROP TABLE IF EXISTS {table}')
        # Limpia las marcas de la app anterior en el historial de migraciones.
        cursor.execute("DELETE FROM django_migrations WHERE app = 'raffle'")


class Migration(migrations.Migration):

    dependencies = [
        ('points', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copy_legacy_participants, migrations.RunPython.noop),
        migrations.RunPython(drop_legacy_tables, migrations.RunPython.noop),
    ]
