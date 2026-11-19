"""Pruebas del sistema de acumulación de puntos."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Participant, PointEntry, Prize, prize_slot_count


def make_participant(name, points=0):
    participant = Participant.objects.create(name=name)
    if points:
        PointEntry.objects.create(participant=participant, points=points)
    return participant


class RankingTests(TestCase):
    """Orden de la clasificación y manejo de empates."""

    def test_ranking_orders_by_points(self):
        make_participant('Ana', 5)
        make_participant('Beto', 12)
        make_participant('Caro', 8)

        from .views import get_ranked_list

        ranked = get_ranked_list()
        self.assertEqual([p.name for _, p in ranked], ['Beto', 'Caro', 'Ana'])
        self.assertEqual([rank for rank, _ in ranked], [1, 2, 3])

    def test_ranking_skips_participants_without_points(self):
        make_participant('Ana', 5)
        make_participant('Sin puntos')

        from .views import get_ranking

        self.assertEqual(get_ranking().count(), 1)

    def test_ties_share_the_same_position(self):
        make_participant('Ana', 7)
        make_participant('Beto', 7)
        make_participant('Caro', 2)

        from .views import get_ranked_list

        ranked = get_ranked_list()
        self.assertEqual([rank for rank, _ in ranked], [1, 1, 3])

    def test_total_points_sums_every_entry(self):
        participant = make_participant('Ana', 3)
        PointEntry.objects.create(participant=participant, points=4)

        self.assertEqual(participant.total_points, 7)


class PublicViewTests(TestCase):
    """Las páginas públicas cargan sin participants ni datos."""

    def setUp(self):
        self.ana = make_participant('Ana', 6)
        self.beto = make_participant('Beto', 10)

    def test_home(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana')
        self.assertContains(response, 'Beto')

    def test_home_without_participants(self):
        Participant.objects.all().delete()
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_leaderboard(self):
        response = self.client.get(reverse('leaderboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beto')

    def test_prizes(self):
        response = self.client.get(reverse('prizes'))
        self.assertEqual(response.status_code, 200)
        # Siempre se muestran los puestos configurados aunque no existan premios.
        self.assertEqual(len(response.context['slots']), prize_slot_count())

    def test_participant_detail(self):
        response = self.client.get(reverse('participant_detail', args=[self.ana.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana')

    def test_participant_detail_404(self):
        response = self.client.get(reverse('participant_detail', args=[999]))
        self.assertEqual(response.status_code, 404)


class PermissionsTests(TestCase):
    """Ingreso de datos: cualquier usuario registrado. Premios: solo staff."""

    def setUp(self):
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.regular = User.objects.create_user('operador', password='x')

    def test_anonymous_is_redirected_to_login(self):
        for url in (
            reverse('add_points'),
            reverse('add_participant'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('login'), response.url)

    def test_registered_user_can_enter_data(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse('add_points')).status_code, 200)
        self.assertEqual(self.client.get(reverse('add_participant')).status_code, 200)

    def test_registered_user_can_create_participant_and_points(self):
        self.client.force_login(self.regular)

        self.client.post(
            reverse('add_participant'), {'name': 'Beto', 'notes': ''}, follow=True
        )
        self.assertTrue(Participant.objects.filter(name='Beto').exists())

        beto = Participant.objects.get(name='Beto')
        self.client.post(
            reverse('add_points'),
            {'participant': beto.id, 'points': 2, 'note': ''},
            follow=True,
        )
        self.assertEqual(PointEntry.objects.count(), 1)

    def test_registered_user_can_delete_point_entry(self):
        participant = make_participant('Ana', 4)
        entry = PointEntry.objects.get()

        self.client.force_login(self.regular)
        self.client.post(reverse('delete_point_entry', args=[entry.id]))

        self.assertEqual(PointEntry.objects.count(), 0)

    def test_prizes_stay_staff_only(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse('edit_prize', args=[1]))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_manage_prizes(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('edit_prize', args=[1])).status_code, 200)


class LoginTests(TestCase):
    """Inicio y cierre de sesión."""

    def setUp(self):
        self.user = User.objects.create_user('operador', password='secreto123')

    def test_login_page_is_public(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'operador', 'password': 'secreto123'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'operador', 'password': 'incorrecta'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertTrue(response.context['form'].errors)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)


class PointsEntryTests(TestCase):
    """Anotar y eliminar puntos."""

    def setUp(self):
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.client.force_login(self.staff)
        self.ana = make_participant('Ana')

    def test_create_participant(self):
        response = self.client.post(
            reverse('add_participant'), {'name': 'Beto', 'notes': ''}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Participant.objects.filter(name='Beto').exists())

    def test_add_points(self):
        response = self.client.post(
            reverse('add_points'),
            {'participant': self.ana.id, 'points': 3, 'note': 'tarde'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        entry = PointEntry.objects.get()
        self.assertEqual(entry.points, 3)
        self.assertEqual(self.ana.total_points, 3)

    def test_add_points_blocked_after_end_date(self):
        with patch('points.views.timezone.localdate', return_value=date(2026, 12, 26)):
            response = self.client.post(
                reverse('add_points'),
                {'participant': self.ana.id, 'points': 3, 'note': ''},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PointEntry.objects.count(), 0)

    def test_add_points_allowed_during_period(self):
        with patch('points.views.timezone.localdate', return_value=date(2026, 11, 20)):
            response = self.client.post(
                reverse('add_points'),
                {'participant': self.ana.id, 'points': 2, 'note': ''},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PointEntry.objects.count(), 1)

    def test_delete_point_entry(self):
        entry = PointEntry.objects.create(participant=self.ana, points=5)

        response = self.client.post(reverse('delete_point_entry', args=[entry.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PointEntry.objects.count(), 0)

    def test_delete_point_entry_requires_post(self):
        entry = PointEntry.objects.create(participant=self.ana, points=5)

        response = self.client.get(reverse('delete_point_entry', args=[entry.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PointEntry.objects.count(), 1)


class AdminTests(TestCase):
    """El panel de administración carga sin errores."""

    def setUp(self):
        self.staff = User.objects.create_superuser('admin', 'admin@test.com', 'x')
        self.client.force_login(self.staff)
        make_participant('Ana', 3)

    def test_admin_list_pages(self):
        for url in (
            '/admin/points/participant/',
            '/admin/points/pointentry/',
            '/admin/points/prize/',
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class PrizeSlotCountTests(TestCase):
    """La cantidad de premios se ajusta con la configuración PRIZE_SLOTS."""

    def setUp(self):
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.client.force_login(self.staff)
        self.ana = make_participant('Ana', 10)
        self.beto = make_participant('Beto', 20)
        self.caro = make_participant('Caro', 15)
        self.dani = make_participant('Dani', 5)

    @override_settings(PRIZE_SLOTS=3)
    def test_prizes_page_shows_configured_amount(self):
        response = self.client.get(reverse('prizes'))
        self.assertEqual(len(response.context['slots']), 3)
        self.assertEqual(response.context['prize_count'], 3)
        self.assertContains(response, 'Top 3')

    @override_settings(PRIZE_SLOTS=3)
    def test_home_shows_configured_amount(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['prize_count'], 3)
        self.assertEqual(len(response.context['top_ranking']), 3)

    @override_settings(PRIZE_SLOTS=3)
    def test_home_hides_prizes_outside_the_top(self):
        for position in range(1, 6):
            Prize.objects.create(position=position, name=f'Premio {position}')

        response = self.client.get(reverse('home'))

        self.assertEqual(len(response.context['prizes']), 3)
        self.assertNotContains(response, 'Premio 5')

    @override_settings(PRIZE_SLOTS=3)
    def test_assign_top_prizes_respects_configured_amount(self):
        for position in range(1, 4):
            Prize.objects.create(position=position, name=f'Premio {position}')

        self.client.post(reverse('assign_top_prizes'))

        self.assertEqual(Prize.objects.get(position=1).winner, self.beto)
        self.assertEqual(Prize.objects.get(position=2).winner, self.caro)
        self.assertEqual(Prize.objects.get(position=3).winner, self.ana)
        self.assertEqual(Prize.objects.count(), 3)

    @override_settings(PRIZE_SLOTS=3)
    def test_position_out_of_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            Prize(position=4, name='Fuera de rango').full_clean()

    @override_settings(PRIZE_SLOTS=8)
    def test_increasing_the_count_allows_more_positions(self):
        Prize(position=8, name='Premio 8º').full_clean()  # no debe lanzar error

    @override_settings(PRIZE_SLOTS=3)
    def test_sync_prizes_keeps_extra_prizes_by_default(self):
        for position in range(1, 6):
            Prize.objects.create(position=position, name=f'Premio {position}')

        call_command('sync_prizes')

        self.assertEqual(Prize.objects.count(), 5)

    @override_settings(PRIZE_SLOTS=3)
    def test_sync_prizes_deletes_extra_prizes_with_flag(self):
        for position in range(1, 6):
            Prize.objects.create(position=position, name=f'Premio {position}')

        call_command('sync_prizes', '--delete-extra')

        self.assertEqual(Prize.objects.count(), 3)
        self.assertEqual(
            sorted(Prize.objects.values_list('position', flat=True)), [1, 2, 3]
        )

    @override_settings(PRIZE_SLOTS=8)
    def test_sync_prizes_creates_missing_prizes(self):
        call_command('sync_prizes')

        self.assertEqual(Prize.objects.count(), 8)
        self.assertEqual(Prize.objects.get(position=8).name, 'Premio 8º lugar')


class PrizeTests(TestCase):
    """Premios del top 5: configuración, asignación y reclamo."""

    def setUp(self):
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.client.force_login(self.staff)
        self.ana = make_participant('Ana', 10)
        self.beto = make_participant('Beto', 20)
        self.caro = make_participant('Caro', 5)

    def test_edit_prize_creates_prize(self):
        response = self.client.post(
            reverse('edit_prize', args=[1]),
            {'name': 'Control de consola', 'description': '', 'winner': self.beto.id},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        prize = Prize.objects.get(position=1)
        self.assertEqual(prize.name, 'Control de consola')
        self.assertEqual(prize.winner, self.beto)

    def test_assign_top_prizes(self):
        count = prize_slot_count()
        for position in range(1, count + 1):
            Prize.objects.create(position=position, name=f'Premio {position}')

        self.client.post(reverse('assign_top_prizes'))

        # Solo hay 3 participantes con puntos, los puestos siguientes quedan libres.
        esperados = {1: self.beto, 2: self.ana, 3: self.caro}
        for position, ganador in esperados.items():
            if position <= count:
                self.assertEqual(Prize.objects.get(position=position).winner, ganador)
        for position in range(4, count + 1):
            self.assertIsNone(Prize.objects.get(position=position).winner)

    def test_claim_prize(self):
        prize = Prize.objects.create(position=1, name='Control', winner=self.beto)

        response = self.client.post(reverse('claim_prize', args=[prize.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        prize.refresh_from_db()
        self.assertTrue(prize.claimed)

    def test_claim_prize_requires_post(self):
        prize = Prize.objects.create(position=1, name='Control', winner=self.beto)

        response = self.client.get(reverse('claim_prize', args=[prize.id]))
        self.assertEqual(response.status_code, 302)
        prize.refresh_from_db()
        self.assertFalse(prize.claimed)
