"""Sincroniza los premios del top N con la configuración PRIZE_SLOTS.

Úsalo después de cambiar ``PRIZE_SLOTS`` en ``rifapp/settings.py``:

    .venv/bin/python manage.py sync_prizes

- Si aumentás la cantidad, crea los premios que faltan (con un nombre por
  defecto) para que puedas configurarlos desde la aplicación.
- Si bajás la cantidad, los premios que quedan fuera del top N se conservan
  (no se borra nada por accidente). Usá ``--delete-extra`` para eliminarlos.
"""

from django.core.management.base import BaseCommand

from points.models import Prize, prize_slot_count


class Command(BaseCommand):
    help = 'Crea o ajusta los premios del top N según la configuración PRIZE_SLOTS.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-extra',
            action='store_true',
            help='Elimina los premios de los puestos que quedan fuera del top N.',
        )

    def handle(self, *args, **options):
        count = prize_slot_count()
        created = []

        for position in range(1, count + 1):
            _, was_created = Prize.objects.get_or_create(
                position=position,
                defaults={'name': f'Premio {position}º lugar'},
            )
            if was_created:
                created.append(position)

        if created:
            lista = ', '.join(f'{p}º' for p in created)
            self.stdout.write(
                self.style.SUCCESS(f'Premios creados para los puestos: {lista}.')
            )
        else:
            self.stdout.write(f'Los premios del 1º al {count}º lugar ya existían.')

        extras = list(Prize.objects.filter(position__gt=count).order_by('position'))
        if not extras:
            return

        detalles = []
        for prize in extras:
            detalle = f'{prize.position}º ({prize.name}'
            if prize.winner_id:
                detalle += f' - ganador: {prize.winner.name}'
            detalles.append(detalle + ')')
        lista = ', '.join(detalles)

        if options['delete_extra']:
            for prize in extras:
                prize.delete()
            self.stdout.write(
                self.style.WARNING(
                    f'Premios eliminados por quedar fuera del top {count}: {lista}.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Hay {len(extras)} premio(s) fuera del top {count}: {lista}. '
                    'Se mantienen en la base; usa --delete-extra para eliminarlos.'
                )
            )
