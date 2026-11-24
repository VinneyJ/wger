# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.

"""
Provisioning API for trusted service accounts.

An app account that has been allowed to add users (``python manage.py add-user-rest <name>``)
can create accounts, switch them on and off, and, if it also has the ``gym.manage_gyms``
permission, create gyms and move its users in and out of them.

A service account only ever sees and changes the users it created itself
(``UserProfile.added_by``). Staff and superuser accounts can never be created or changed here.
"""

# Django
from django.contrib.auth.models import (
    Group,
    User,
)
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

# Third Party
from allauth.account.models import EmailAddress
from rest_framework import (
    mixins,
    serializers,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

# wger
from wger.core.api.permissions import AllowRegisterUser
from wger.gym.helpers import is_any_gym_admin
from wger.gym.models import (
    Gym,
    GymUserConfig,
)


GYM_MEMBER_GROUP = 'gym_member'


class CanManageGyms(BasePermission):
    """
    The service account must also hold wger's own "manage all gyms" permission
    """

    def has_permission(self, request, view):
        return request.user.has_perm('gym.manage_gyms')


#
# Serializers
#
class ProvisionedUserSerializer(serializers.ModelSerializer):
    """
    A user created by a service account
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        style={'input_type': 'password'},
        help_text='Optional. Without it the account has no password and signs in another way '
        '(for example a password reset link or single sign-on).',
    )
    gym = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'gym',
            'password',
        )
        read_only_fields = ('id', 'is_active', 'gym')

    def get_gym(self, obj) -> int | None:
        return obj.userprofile.gym_id

    def validate_username(self, value):
        if self.instance is not None:
            return value
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        if self.instance is not None:
            return value
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email address is already in use.')
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        if password:
            validate_password(password, User(username=attrs.get('username', '')))
        return attrs

    def update(self, instance, validated_data):
        # Username, email and password are set once, at creation. Only names can change.
        for field in ('username', 'email', 'password'):
            validated_data.pop(field, None)
        return super().update(instance, validated_data)


class GymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = ('id', 'name')


class GymMemberSerializer(serializers.Serializer):
    user = serializers.IntegerField(help_text='ID of a user created by this service account')


#
# Views
#
class ProvisionedUserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Create and manage user accounts on behalf of a service account.

    Only the users this account created are visible. Accounts are never deleted here:
    switch them off with ``deactivate`` (their data is kept) and back on with ``activate``.
    """

    serializer_class = ProvisionedUserSerializer
    permission_classes = (AllowRegisterUser,)
    http_method_names = ('get', 'post', 'patch', 'head', 'options')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        return (
            User.objects.filter(
                userprofile__added_by=self.request.user,
                is_staff=False,
                is_superuser=False,
            )
            .select_related('userprofile')
            .order_by('id')
        )

    @transaction.atomic
    def perform_create(self, serializer):
        password = serializer.validated_data.pop('password', None)
        user = User(**serializer.validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        # The profile is created by a signal
        user.userprofile.added_by = self.request.user
        user.userprofile.save()

        if user.email:
            EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)

        serializer.instance = user

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Switch the account off. The user can no longer sign in; nothing is deleted."""
        return self._set_active(False)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Switch the account back on."""
        return self._set_active(True)

    def _set_active(self, active):
        user = self.get_object()
        if user.is_active != active:
            user.is_active = active
            user.save(update_fields=['is_active'])
        return Response(self.get_serializer(user).data)


class ProvisionedGymViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Create and rename gyms, and move the service account's users in and out of them.

    Needs both the "add users via the API" flag and the ``gym.manage_gyms`` permission.
    """

    serializer_class = GymSerializer
    permission_classes = (AllowRegisterUser, CanManageGyms)
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')
    queryset = Gym.objects.all().order_by('id')

    def _own_user(self, user_id):
        return (
            User.objects.filter(
                pk=user_id,
                userprofile__added_by=self.request.user,
                is_staff=False,
                is_superuser=False,
            )
            .select_related('userprofile')
            .first()
        )

    @action(detail=True, methods=['get', 'post'], serializer_class=GymMemberSerializer)
    def members(self, request, pk=None):
        """
        GET: the members of this gym that this service account created.
        POST ``{"user": <id>}``: put one of this account's users into the gym
        (moving them out of any other gym).
        """
        gym = self.get_object()

        if request.method == 'GET':
            users = User.objects.filter(
                userprofile__gym=gym,
                userprofile__added_by=request.user,
                is_staff=False,
                is_superuser=False,
            ).order_by('id')
            page = self.paginate_queryset(users)
            data = ProvisionedUserSerializer(page if page is not None else users, many=True).data
            return self.get_paginated_response(data) if page is not None else Response(data)

        serializer = GymMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._own_user(serializer.validated_data['user'])
        if user is None:
            return Response({'user': ['Unknown user.']}, status=status.HTTP_400_BAD_REQUEST)
        if is_any_gym_admin(user):
            return Response(
                {'user': ['This user is gym staff (trainer or manager). Manage them in wger.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user.userprofile.gym = gym
            user.userprofile.save()
            GymUserConfig.objects.update_or_create(user=user, defaults={'gym': gym})
            user.groups.add(Group.objects.get(name=GYM_MEMBER_GROUP))

        return Response(ProvisionedUserSerializer(user).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path=r'members/(?P<user_id>\d+)')
    def remove_member(self, request, pk=None, user_id=None):
        """Take one of this account's users out of the gym. The account itself stays."""
        gym = self.get_object()
        user = self._own_user(user_id)
        if user is None or user.userprofile.gym_id != gym.pk:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if is_any_gym_admin(user):
            return Response(
                {'user': ['This user is gym staff (trainer or manager). Manage them in wger.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user.userprofile.gym = None
            user.userprofile.save()
            GymUserConfig.objects.filter(user=user).delete()
            user.groups.remove(Group.objects.get(name=GYM_MEMBER_GROUP))

        return Response(status=status.HTTP_204_NO_CONTENT)
