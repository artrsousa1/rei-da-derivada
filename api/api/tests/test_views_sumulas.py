from rest_framework.test import APITestCase
from django.urls import reverse
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.test import APIClient
from api.models import Sumula, Event, PlayerScore, Token, Player
from users.models import User
import uuid
from ..utils import get_permissions, get_content_type
from django.contrib.auth.models import Group


class SumulaViewTest(APITestCase):
    def create_unique_email(self):
        return f'{uuid.uuid4()}@gmail.com'

    def create_unique_username(self):
        return f'user_{uuid.uuid4().hex[:10]}'

    def setUpData(self):
        self.data = [
            {
                "id": self.sumula.id,
                "active": True,
                "referee": [
                    {
                        "id": self.user.id,
                        "first_name": self.user.first_name,
                        "last_name": self.user.last_name
                    },
                    {
                        "id": self.user2.id,
                        "first_name": self.user2.first_name,
                        "last_name": self.user2.last_name
                    }
                ],
                "name": "imortais 01",
                "players_score": [
                    {
                        "id": self.player_score1.id,
                        "points": 10,
                        "player": {
                            "id": self.player.id,
                            "total_score": 0,
                            "registration_email": self.player.registration_email,
                            "event": self.event.id,
                            "user": {
                                "id": self.user_player1.id,
                                "first_name": self.user_player1.first_name,
                                "last_name": self.user_player1.last_name
                            }
                        }
                    },
                    {
                        "id": self.player_score2.id,
                        "points": 15,
                        "player": {
                            "id": self.player2.id,
                            "total_score": 0,
                            "registration_email": self.player2.registration_email,
                            "event": self.event.id,
                            "user": {
                                "id": self.user_player2.id,
                                "first_name": self.user_player2.first_name,
                                "last_name": self.user_player2.last_name
                            }
                        }
                    }
                ]
            }
        ]

    def setUpSumula(self):
        self.sumula = Sumula.objects.create(event=self.event)
        self.sumula2 = Sumula.objects.create(event=self.event)
        self.sumula3 = Sumula.objects.create(event=self.event)

    def setupUser(self):
        self.user = User.objects.create(
            username=self.create_unique_username(), email=f'{uuid.uuid4()}@gmail.com', first_name='Teste', last_name='User')
        self.user.save()
        self.user2 = User.objects.create(
            username=self.create_unique_username(), email=self.create_unique_email(), first_name='Teste', last_name='User')
        self.user2.save()
        self.user_player1 = User.objects.create(
            username=self.create_unique_username(), email=self.create_unique_email(), first_name='Teste', last_name='User')
        self.user_player1.save()

        self.user_player2 = User.objects.create(
            username=self.create_unique_username(), email=self.create_unique_email(), first_name='Teste', last_name='User')
        self.user_player2.save()

    def setUpReferee(self, user: User, user2: User, sumulas: list):
        for sumula in sumulas:
            sumula.referee.add(user)
            sumula.referee.add(user2)

    def setUpPlayers(self):
        self.player = Player.objects.create(
            user=self.user_player1, event=self.event, registration_email=self.create_unique_email())
        self.player2 = Player.objects.create(
            user=self.user_player2, event=self.event, registration_email=self.create_unique_email())

    def setUpPlayerScore(self):
        self.player_score1 = PlayerScore.objects.create(
            player=self.player, sumula=self.sumula, event=self.event)
        self.player_score2 = PlayerScore.objects.create(
            player=self.player2, sumula=self.sumula, event=self.event)

    def setUpPermissions(self):
        self.sumula_content_type = get_content_type(Sumula)
        self.permission = get_permissions(self.sumula_content_type)
        self.group = Group.objects.create(name='Grupo_teste')
        self.group.permissions.set(self.permission)
        self.user.groups.add(self.group)

    def setUpEvent(self):
        self.token = Token.objects.create()
        self.event = Event.objects.create(name='Evento 1', token=self.token)

    def setUp(self):
        self.client = APIClient()
        self.setUpEvent()
        self.setUpSumula()
        self.setupUser()
        self.setUpReferee(self.user, self.user2, [
            self.sumula, self.sumula2, self.sumula3])
        self.setUpPlayers()
        self.setUpPlayerScore()
        self.setUpPermissions()
        self.url = f"{reverse('api:sumula')}?event_id={self.event.id}"
        self.url_update = f"{reverse('api:sumula')}?sumula_id={self.sumula.id}"
        self.setUpData()

    """*********Testes de Create*********"""

    def test_create_sumula(self):
        PlayerScore.objects.all().delete()
        self.assertFalse(PlayerScore.objects.exists())
        data = {
            'players': [{'user_id': self.player.id}, {'user_id': self.player2.id}]
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Sumula.objects.count(), 4)
        self.assertEqual(PlayerScore.objects.count(), 2)

    def test_create_sumula_unauthenticated(self):
        data = {
            'players': [{'user_id': self.user.id}]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_sumula_invalid_data(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sumula_invalid_data2(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {'players': [{}]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sumula_unauthorized(self):
        self.user.groups.remove(self.group)
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    """*********Testes de GET*********"""

    def test_get_sumulas(self):

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {'event_id': self.event.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 3)

    def test_get_active_sumulas(self):
        url = f"{reverse('api:sumula-ativas')}?event_id={self.event.id}"
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url, {'event_id': self.event.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_get_sumulas_unauthenticated(self):
        response = self.client.get(self.url, {'event_id': self.event.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_sumulas_unauthorized(self):
        self.user.groups.remove(self.group)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {'event_id': self.event.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    """*********Testes de update*********"""

    def test_update_sumula(self):

        data = self.data
        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url_update, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        sumula = Sumula.objects.get(id=self.sumula.id)
        referees = sumula.referee.all()
        scores = sumula.scores.all()

        self.assertIsNotNone(sumula)
        self.assertEqual(len(referees), 2)
        self.assertEqual(len(scores), 2)
        self.assertEqual(sumula.name, 'imortais 01')
        self.assertEqual(sumula.referee.count(), 2)
        self.assertEqual(sumula.scores.count(), 2)
        self.assertFalse(Sumula.objects.get(id=self.sumula.id).active)

        for referee in referees:
            self.assertIn(referee, [self.user, self.user2])
            self.assertEqual(referee.first_name, 'Teste')

        for score in scores:
            self.assertIn(score.player, [self.player, self.player2])
            self.assertIn(score.points, [10, 15])
            self.assertEqual(score.player.total_score, score.points)

    def test_update_sumula_unauthenticated(self):

        data = self.data
        response = self.client.put(self.url_update, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_sumula_invalid_data(self):

        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url_update, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_sumula_unauthorized(self):
        self.user.groups.remove(self.group)
        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url_update, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_sumula_not_found(self):
        self.client.force_authenticate(user=self.user)
        data = self.data
        data[0]['id'] = 100
        response = self.client.put(self.url_update, format='json', data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['errors'], 'Sumula não encontrada!')

    def test_update_sumula_without_player_score_id(self):
        data = self.data
        data[0]['players_score'][0].pop('id')
        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url_update, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['errors'], 'Dados inválidos!')

    def test_update_sumula_with_i_player_score_id_not_found(self):
        data = self.data
        data[0]['players_score'][0]['id'] = 100
        self.client.force_authenticate(user=self.user)
        response = self.client.put(self.url_update, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['errors'], 'Dados inválidos!')

    def tearDown(self):
        User.objects.all().delete()
        Sumula.objects.all().delete()
        Event.objects.all().delete()
        PlayerScore.objects.all().delete()
        Token.objects.all().delete()
        Player.objects.all().delete()
        Group.objects.all().delete()
        self.data = None