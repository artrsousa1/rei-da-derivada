from rest_framework import status, request, response
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission
from .base_views import BaseSumulaView, SUMULA_NOT_FOUND_ERROR_MESSAGE, SUMULA_ID_NOT_PROVIDED_ERROR_MESSAGE
from api.models import Staff, SumulaClassificatoria, SumulaImortal, PlayerScore, Player
from ..serializers import SumulaSerializer, SumulaForPlayerSerializer, SumulaImortalSerializer, SumulaClassificatoriaSerializer, SumulaClassificatoriaForPlayerSerializer, SumulaImortalForPlayerSerializer
from rest_framework.permissions import BasePermission
from ..utils import handle_400_error
from ..swagger import Errors, sumula_imortal_api_put_schema, sumula_classicatoria_api_put_schema, sumulas_response_schema, manual_parameter_event_id
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

SUMULA_IS_CLOSED_ERROR_MESSAGE = "Súmula já encerrada só pode ser editada por um gerente ou adminstrador!"


class HasSumulaPermission(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:

        if request.method == 'POST':
            return request.user.has_perm('api.add_sumula_event', obj)
        elif request.method == 'GET':
            return request.user.has_perm('api.view_sumula_event', obj)
        elif request.method == 'PUT':
            return request.user.has_perm('api.change_sumula_event', obj)
        elif request.method == 'DELETE':
            return request.user.has_perm('api.delete_sumula_event', obj)
        return True


class GetSumulasView(BaseSumulaView):
    """Lida com os requests relacionados a sumulas."""
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Retorna todas as sumulas associadas a um evento.",
        operation_description="Retorna todas as sumulas associadas a um evento com seus jogadores e pontuações.",
        security=[{'Bearer': []}],
        manual_parameters=manual_parameter_event_id,
        responses={200: openapi.Response('OK', sumulas_response_schema), **Errors([400]).retrieve_erros()})
    def get(self, request: request.Request, *args, **kwargs) -> response.Response:
        """Retorna todas as sumulas associadas a um evento."""
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)
        sumulas_imortal, sumulas_classificatoria = self.get_sumulas(
            event=event)
        data = SumulaSerializer(
            {'sumula_classificatoria': sumulas_classificatoria, 'sumula_imortal': sumulas_imortal}).data
        return response.Response(status=status.HTTP_200_OK, data=data)


class SumulaClassificatoriaView(BaseSumulaView):
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Cria uma nova sumula classificatoria.",
        operation_description="Cria uma nova sumula classificatoria e retorna a sumula criada com os jogadores e suas pontuações.",
        security=[{'Bearer': []}],
        manual_parameters=manual_parameter_event_id,
        request_body=openapi.Schema(
            title='Sumula',
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Nome da sumula'),
                'players': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    title='Players',
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID do jogador'),
                            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Nome do jogador'),
                        }
                    ),
                    description='Lista de jogadores',
                ),
                'referees': openapi.Schema(
                    type=openapi.TYPE_ARRAY, title='Staffs',
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID do Staff')}),
                    description='Lista de objetos Staff'),
            },
            required=['name', 'players'],
        ),
        responses={201: openapi.Response(
            'Created', SumulaClassificatoriaSerializer), **Errors([400]).retrieve_erros()}
    )
    def post(self, request: request.Request, *args, **kwargs) -> response.Response:
        """Cria uma nova sumula classificatoria e retorna a sumula criada.

        Permissões necessárias: IsAuthenticated, HasSumulaPermission
        """
        if not self.validate_request_data_dict(request.data) or 'name' not in request.data or not self.validate_players(request.data) or not self.validate_referees(request.data):
            return handle_400_error("Dados inválidos!")
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)
        name = request.data['name']
        players = request.data['players']
        sumula = SumulaClassificatoria.objects.create(event=event, name=name)
        try:
            self.create_players_score(
                players=players, sumula=sumula, event=event)
        except Exception as e:
            return handle_400_error(str(e))
        referees = request.data['referees']
        self.add_referees(sumula=sumula, event=event, referees=referees)
        data = SumulaClassificatoriaSerializer(sumula).data
        return response.Response(status=status.HTTP_201_CREATED, data=data)

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Encerra uma sumula classificatoria.",
        operation_description="""Esta rota serve para salvar os dados da sumula e marcar a sumula como **encerrada**.
        As pontuações dos jogadores devem ser enviadas no corpo da requisição e serão atualizadas no banco de dados.
        Devem ser enviados os jogadores **não-classificados** como **IMORTAIS** (is_imortal = True). Já os jogadores **classificados** devem ser enviados como **is_imortal = False.**
        A sumula **não** pode ser mais salva/editada por um monitor comum após encerrada.
        Apenas um gerente ou administrador do evento pode editar uma sumula encerrada.""",
        security=[{'Bearer': []}],
        manual_parameters=manual_parameter_event_id,
        request_body=sumula_classicatoria_api_put_schema,
        responses={200: openapi.Response('OK'), **Errors([400]).retrieve_erros()})
    def put(self, request: request.Request, *args, **kwargs):
        """Atualiza uma sumula de Classificatoria
        Obtém o id da sumula a ser atualizada e atualiza os dados associados a ela.
        Obtém uma lista da pontuação dos jogadores e atualiza as pontuações associados a sumula.
        Marca a sumula como encerrada."""

        required_fields = ['id', 'name', 'description']
        if not self.validate_request_data_dict(request.data) or not all(field in request.data for field in required_fields):
            return handle_400_error("Dados inválidos!")
        if not self.validate_players_score(request.data):
            return handle_400_error("Dados Invalidos!")
        sumula_id = request.data['id']
        if not sumula_id:
            return handle_400_error(SUMULA_ID_NOT_PROVIDED_ERROR_MESSAGE)
        sumula = SumulaClassificatoria.objects.filter(id=sumula_id).first()
        if not sumula:
            return handle_400_error(SUMULA_NOT_FOUND_ERROR_MESSAGE)
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(request, event)
        is_admin = request.user.email == event.admin_email
        if not is_admin:
            try:
                staff = self.validate_if_staff_is_sumula_referee(
                    sumula=sumula, event=event)
            except Exception as e:
                return handle_400_error(str(e))
            if not sumula.active and not staff.is_manager:
                return handle_400_error(SUMULA_IS_CLOSED_ERROR_MESSAGE)

        try:
            self.update_sumula(sumula=sumula, event=event)
        except Exception as e:
            return handle_400_error(str(e))
        return response.Response(status=status.HTTP_200_OK)


class SumulaImortalView(BaseSumulaView):
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Cria uma nova sumula imortal.",
        operation_description="Cria uma nova sumula imortal e retorna a sumula criada com os jogadores e suas pontuações.",
        security=[{'Bearer': []}],
        manual_parameters=manual_parameter_event_id,
        request_body=openapi.Schema(
            title='Sumula',
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Nome da sumula'),
                'players': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    title='Players',
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID do jogador'),
                            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Nome do jogador'),
                        }
                    ),
                    description='Lista de jogadores',
                ),
                'referees': openapi.Schema(
                    type=openapi.TYPE_ARRAY, title='Staffs',
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID do Staff')}),
                    description='Lista de objetos Staff'),
            },
            required=['name', 'players'],
        ),
        responses={201: openapi.Response(
            'Created', SumulaImortalSerializer), **Errors([400]).retrieve_erros()}
    )
    def post(self, request: request.Request, *args, **kwargs) -> response.Response:
        """Cria uma nova sumula imortal e retorna a sumula criada.

        Permissões necessárias: IsAuthenticated, HasSumulaPermission
        """
        if not self.validate_request_data_dict(request.data) or 'name' not in request.data or not self.validate_players(request.data) or not self.validate_referees(request.data):
            return handle_400_error("Dados inválidos!")
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)

        players = request.data['players']
        name = request.data['name']
        sumula = SumulaImortal.objects.create(
            event=event, name=name)
        try:
            self.create_players_score(
                players=players, sumula=sumula, event=event)
        except Exception as e:
            return handle_400_error(str(e))
        referees = request.data['referees']
        self.add_referees(sumula=sumula, event=event, referees=referees)
        data = SumulaImortalSerializer(sumula).data
        return response.Response(status=status.HTTP_201_CREATED, data=data)

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Encerra uma sumula imortal.",
        operation_description="""Esta rota serve para salvar os dados da sumula e marcar a sumula como **encerrada**.
        As pontuações dos jogadores devem ser enviadas no corpo da requisição e serão atualizadas no banco de dados.
        A sumula **não** pode ser mais salva/editada por um monitor comum após encerrada.
        Apenas um gerente ou administrador do evento pode editar uma sumula encerrada.
        """,
        security=[{'Bearer': []}],
        manual_parameters=manual_parameter_event_id,
        request_body=sumula_imortal_api_put_schema,
        responses={200: openapi.Response('OK'), **Errors([400]).retrieve_erros()})
    def put(self, request: request.Request, *args, **kwargs) -> response.Response:
        """Atualiza uma sumula Imortal
        Obtém o id da sumula a ser atualizada e atualiza os dados associados a ela.
        Obtém uma lista da pontuação dos jogadores e atualiza as pontuações associados a sumula.
        Marca a sumula como encerrada.
        """
        required_fields = ['id', 'name', 'description']
        if not self.validate_request_data_dict(request.data) or not all(field in request.data for field in required_fields):
            return handle_400_error("Dados inválidos!")
        sumula_id = request.data['id']
        if not sumula_id:
            return handle_400_error(SUMULA_ID_NOT_PROVIDED_ERROR_MESSAGE)
        sumula = SumulaImortal.objects.filter(id=sumula_id).first()
        if not sumula:
            return handle_400_error(SUMULA_NOT_FOUND_ERROR_MESSAGE)
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(request, event)
        is_admin = request.user.email == event.admin_email
        if not is_admin:
            try:
                staff = self.validate_if_staff_is_sumula_referee(
                    sumula=sumula, event=event)
            except Exception as e:
                return handle_400_error(str(e))
            if not sumula.active and not staff.is_manager:
                return handle_400_error(SUMULA_IS_CLOSED_ERROR_MESSAGE)

        try:
            self.update_sumula(sumula=sumula, event=event)
        except Exception as e:
            return handle_400_error(str(e))
        return response.Response(status=status.HTTP_200_OK)


class ActiveSumulaView(BaseSumulaView):
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Retorna todas as sumulas ativas associadas a um evento.",
        operation_description="Retorna todas as sumulas ativas associadas a um evento, com seus jogadores e pontuações.",
        manual_parameters=manual_parameter_event_id,
        responses={200: openapi.Response(
            'OK', sumulas_response_schema), **Errors([400]).retrieve_erros()}
    )
    def get(self, request: request.Request):
        """Retorna todas as sumulas ativas."""
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)
        sumula_imortal, sumula_classificatoria = self.get_sumulas(
            event=event, active=True)
        data = SumulaSerializer(
            {'sumula_classificatoria': sumula_classificatoria, 'sumula_imortal': sumula_imortal}).data
        return response.Response(status=status.HTTP_200_OK, data=data)


class FinishedSumulaView(BaseSumulaView):
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Retorna todas as sumulas encerradas associadas a um evento.",
        operation_description="Retorna todas as sumulas encerradas associadas a um evento, com seus jogadores e pontuações.",
        manual_parameters=manual_parameter_event_id,
        responses={200: openapi.Response(
            'OK', sumulas_response_schema), **Errors([400]).retrieve_erros()}
    )
    def get(self, request: request.Request):
        """Retorna todas as sumulas encerradas."""
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)
        sumula_imortal, sumula_classificatoria = self.get_sumulas(
            event=event, active=False)
        data = SumulaSerializer(
            {'sumula_classificatoria': sumula_classificatoria, 'sumula_imortal': sumula_imortal}).data
        return response.Response(status=status.HTTP_200_OK, data=data)


class GetSumulaForPlayerPermission(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method == 'GET':
            return request.user.has_perm('api.view_event', obj)
        return False


class GetSumulaForPlayer(BaseSumulaView):
    permission_classes = [IsAuthenticated, GetSumulaForPlayerPermission]

    @ swagger_auto_schema(
        tags=['sumula'],
        operation_summary="Retorna as sumulas ativas para um jogador.",
        operation_description="""
        Retorna todas as sumulas ativas para o jogador. São omitidos pontuações da sumula.""",
        manual_parameters=manual_parameter_event_id,
        responses={200: openapi.Response(
            'OK', SumulaForPlayerSerializer), **Errors([400]).retrieve_erros()}
    )
    def get(self, request: request.Request, *args, **kwargs) -> response.Response:
        """Retorna todas as sumulas ativas associadas a um jogador."""
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)

        player = Player.objects.filter(user=request.user, event=event).first()
        if not player:
            return handle_400_error("Jogador não encontrado!")

        if player.is_imortal:
            player_scores = PlayerScore.objects.filter(
                player=player, sumula_imortal__active=True)
            if not player_scores:
                return handle_400_error("Jogador não possui nenhuma sumula associada!")
            sumulas = [
                player_score.sumula_imortal for player_score in player_scores]
            data = SumulaImortalForPlayerSerializer(
                sumulas, many=True).data
        else:
            player_scores = PlayerScore.objects.filter(
                player=player, sumula_classificatoria__active=True)
            if not player_scores:
                return handle_400_error("Jogador não possui nenhuma sumula associada!")
            sumulas = [
                player_score.sumula_classificatoria for player_score in player_scores]
            data = SumulaClassificatoriaForPlayerSerializer(
                sumulas, many=True).data

        return response.Response(status=status.HTTP_200_OK, data=data)


class AddRefereeToSumulaView(BaseSumulaView):
    permission_classes = [IsAuthenticated, HasSumulaPermission]

    @swagger_auto_schema(
        tags=['sumula'],
        operation_description="""
        Adiciona um árbitro a uma súmula que já existe.
        Caso uma súmula seja criada sem nenhum árbitro, é possível que um usuário monitor se auto adicione como árbitro ao selecionar a sumula desejada.
        Apenas o usuário que fez a requisição será adicionado como árbitro da súmula.
        Esta rota verifica se o usuário em questão tem as permissões necessárias para ser um árbitro no evento e se possui um objeto staff associado a ele.

            É necessário fornecer o id da súmula e indicar se a súmula é imortal ou classificatória no corpo da requisição.
        """,
        operation_summary="Adiciona um árbitro a uma súmula.",
        request_body=openapi.Schema(
            title='Sumula',
            type=openapi.TYPE_OBJECT,
            properties={
                'sumula_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Id da sumula imortal'),
                'is_imortal': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Indica se a sumula é imortal ou classificatória', example=True)
            },
            required=['sumula_id', 'is_imortal'],
        ),
        manual_parameters=manual_parameter_event_id,
        responses={200: openapi.Response('OK'), **Errors([400]).retrieve_erros()})
    def put(self, request: request.Request, *args, **kwargs):
        if not self.validate_request_data_dict(request.data) or 'sumula_id' not in request.data or 'is_imortal' not in request.data:
            return handle_400_error("Dados inválidos!")
        sumula_id = request.data.get('sumula_id')
        if not sumula_id:
            return handle_400_error(SUMULA_ID_NOT_PROVIDED_ERROR_MESSAGE)
        try:
            event = self.get_object()
        except Exception as e:
            return handle_400_error(str(e))
        self.check_object_permissions(self.request, event)
        staff = Staff.objects.filter(user=request.user, event=event).first()
        if not staff:
            return handle_400_error("Usuário não é um monitor do evento!")
        is_imortal = request.data.get('is_imortal')
        if is_imortal:
            sumula = SumulaImortal.objects.filter(id=sumula_id).first()
        else:
            sumula = SumulaClassificatoria.objects.filter(id=sumula_id).first()
        if not sumula:
            return handle_400_error(SUMULA_NOT_FOUND_ERROR_MESSAGE)
        if sumula.referee.all().count() > 0:
            return handle_400_error("Súmula já possui um ou mais árbitros!")
        sumula.referee.add(staff)
        return response.Response(status=status.HTTP_200_OK)
