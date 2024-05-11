from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from api.models import Token, Event, Sumula, PlayerScore, Player
from users.models import User


class UserSerializer(ModelSerializer):
    """ Serializer for the User model.
    fields: first_name, last_name, id
    """
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']


class PlayerSerializer(ModelSerializer):
    """ Serializer for the Player model.
    fields: first_name, last_name, event, total_score, registration_email, id
    """
    user = UserSerializer()

    class Meta:
        model = Player
        fields = ['id', 'total_score', 'registration_email', 'event', 'user']


class TokenSerializer(ModelSerializer):
    class Meta:
        model = Token
        fields = ['token_code']


class EventSerializer(ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'name']


class PlayerScoreSerializer(ModelSerializer):
    player = PlayerSerializer()

    class Meta:
        model = PlayerScore
        fields = ['id', 'player', 'sumula', 'points']


class PlayerScoreSerializerForSumula(ModelSerializer):
    player = PlayerSerializer()

    class Meta:
        model = PlayerScore
        fields = ['id', 'points', 'player']


class SumulaSerializer(ModelSerializer):
    """ Serializer for the Sumula model.
    fields: id, name, players_score
    returns: players_score as a list of PlayerScoreSerializer
    """
    players_score = PlayerScoreSerializerForSumula(
        source='scores', many=True)
    referee = UserSerializer(many=True)

    class Meta:
        model = Sumula
        fields = ['id', 'active', 'referee', 'name', 'players_score']