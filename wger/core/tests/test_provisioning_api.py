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

# Django
from django.contrib.auth.models import (
    Group,
    User,
)
from django.urls import reverse

# Third Party
from allauth.account.models import EmailAddress

# wger
from wger.core.tests.base_testcase import WgerTestCase
from wger.gym.models import (
    Gym,
    GymConfig,
    GymUserConfig,
)


STRONG_PASSWORD = 'correct-horse-battery-41'


class ProvisioningBase(WgerTestCase):
    """
    In the fixtures, user 'test' may add users via the API (can_add_user) and has
    already added 'trainer1' and 'trainer2'.
    """

    users_url = reverse('provisioning-user-list')
    gyms_url = reverse('provisioning-gym-list')

    def user_url(self, pk, action=None):
        if action:
            return reverse(f'provisioning-user-{action}', kwargs={'pk': pk})
        return reverse('provisioning-user-detail', kwargs={'pk': pk})

    def create_user(self, **data):
        payload = {'username': 'newmember', 'email': 'new@example.com', **data}
        return self.client.post(self.users_url, payload, content_type='application/json')


class ProvisioningUserAccessTestCase(ProvisioningBase):
    def test_anonymous_is_rejected(self):
        response = self.create_user()
        self.assertIn(response.status_code, (401, 403))

    def test_account_without_flag_is_rejected(self):
        # 'admin' is a superuser but has not been allowed to add users via the API
        self.user_login('admin')
        self.assertEqual(self.create_user().status_code, 403)
        self.assertEqual(self.client.get(self.users_url).status_code, 403)
        self.assertFalse(User.objects.filter(username='newmember').exists())


class ProvisioningUserTestCase(ProvisioningBase):
    def setUp(self):
        super().setUp()
        self.user_login('test')

    def test_create_with_password(self):
        response = self.create_user(password=STRONG_PASSWORD, first_name='New')

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertNotIn('password', body)
        self.assertTrue(body['is_active'])
        self.assertIsNone(body['gym'])

        user = User.objects.get(username='newmember')
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.userprofile.added_by.username, 'test')
        self.assertFalse(user.is_staff)
        email = EmailAddress.objects.get(user=user)
        self.assertTrue(email.primary)
        self.assertFalse(email.verified)

    def test_create_without_password_has_no_usable_password(self):
        response = self.create_user()

        self.assertEqual(response.status_code, 201)
        self.assertFalse(User.objects.get(username='newmember').has_usable_password())

    def test_weak_password_is_rejected(self):
        response = self.create_user(password='123')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='newmember').exists())

    def test_duplicate_username_and_email_are_rejected(self):
        self.assertEqual(self.create_user(username='DEMO').status_code, 400)
        existing_email = User.objects.get(username='demo').email or 'demo-taken@example.com'
        User.objects.filter(username='demo').update(email=existing_email)
        self.assertEqual(self.create_user(email=existing_email.upper()).status_code, 400)

    def test_cannot_create_staff(self):
        response = self.create_user(is_staff=True, is_superuser=True)

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='newmember')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_list_shows_only_own_users(self):
        self.create_user()

        response = self.client.get(self.users_url)

        self.assertEqual(response.status_code, 200)
        names = {u['username'] for u in response.json()['results']}
        self.assertEqual(names, {'trainer1', 'trainer2', 'newmember'})

    def test_other_users_are_not_found(self):
        demo = User.objects.get(username='demo')
        self.assertEqual(self.client.get(self.user_url(demo.pk)).status_code, 404)
        self.assertEqual(self.client.post(self.user_url(demo.pk, 'deactivate')).status_code, 404)
        self.assertTrue(User.objects.get(username='demo').is_active)

    def test_deactivate_and_activate(self):
        self.create_user(password=STRONG_PASSWORD)
        user = User.objects.get(username='newmember')

        response = self.client.post(self.user_url(user.pk, 'deactivate'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_active'])
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # A switched-off account can't sign in, and its data is still there
        self.client.logout()
        self.assertFalse(self.client.login(username='newmember', password=STRONG_PASSWORD))
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

        self.user_login('test')
        response = self.client.post(self.user_url(user.pk, 'activate'))
        self.assertTrue(response.json()['is_active'])
        self.client.logout()
        self.assertTrue(self.client.login(username='newmember', password=STRONG_PASSWORD))

    def test_patch_changes_names_only(self):
        self.create_user()
        user = User.objects.get(username='newmember')

        response = self.client.patch(
            self.user_url(user.pk),
            {
                'first_name': 'Dennis',
                'username': 'hijack',
                'email': 'other@example.com',
                'is_active': False,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Dennis')
        self.assertEqual(user.username, 'newmember')
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.is_active)

    def test_users_cannot_be_deleted(self):
        self.create_user()
        user = User.objects.get(username='newmember')

        self.assertEqual(self.client.delete(self.user_url(user.pk)).status_code, 405)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


class ProvisioningGymTestCase(ProvisioningBase):
    def setUp(self):
        super().setUp()
        test = User.objects.get(username='test')
        test.groups.add(Group.objects.get(name='general_gym_manager'))
        self.user_login('test')
        self.create_user()
        self.member = User.objects.get(username='newmember')

    def members_url(self, gym_pk, user_pk=None):
        if user_pk is not None:
            return reverse(
                'provisioning-gym-remove-member', kwargs={'pk': gym_pk, 'user_id': user_pk}
            )
        return reverse('provisioning-gym-members', kwargs={'pk': gym_pk})

    def add(self, gym_pk, user_pk):
        return self.client.post(
            self.members_url(gym_pk), {'user': user_pk}, content_type='application/json'
        )

    def test_needs_manage_gyms_permission(self):
        Group.objects.get(name='general_gym_manager').user_set.remove(
            User.objects.get(username='test')
        )
        self.assertEqual(self.client.get(self.gyms_url).status_code, 403)

    def test_create_and_rename_gym(self):
        response = self.client.post(
            self.gyms_url, {'name': 'Northside'}, content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        gym = Gym.objects.get(pk=response.json()['id'])
        self.assertTrue(GymConfig.objects.filter(gym=gym).exists())

        response = self.client.patch(
            reverse('provisioning-gym-detail', kwargs={'pk': gym.pk}),
            {'name': 'Northside Strength'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        gym.refresh_from_db()
        self.assertEqual(gym.name, 'Northside Strength')

    def test_gyms_cannot_be_deleted(self):
        response = self.client.delete(reverse('provisioning-gym-detail', kwargs={'pk': 1}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Gym.objects.filter(pk=1).exists())

    def test_add_move_list_and_remove_member(self):
        response = self.add(1, self.member.pk)
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.userprofile.gym_id, 1)
        self.assertEqual(GymUserConfig.objects.get(user=self.member).gym_id, 1)
        self.assertTrue(self.member.groups.filter(name='gym_member').exists())

        # Moving to another gym leaves exactly one membership
        self.assertEqual(self.add(2, self.member.pk).status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.userprofile.gym_id, 2)
        self.assertEqual(GymUserConfig.objects.filter(user=self.member).count(), 1)

        listed = self.client.get(self.members_url(2)).json()
        listed = listed['results'] if isinstance(listed, dict) else listed
        self.assertEqual([u['username'] for u in listed], ['newmember'])

        response = self.client.delete(self.members_url(2, self.member.pk))
        self.assertEqual(response.status_code, 204)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.userprofile.gym_id)
        self.assertFalse(GymUserConfig.objects.filter(user=self.member).exists())
        self.assertFalse(self.member.groups.filter(name='gym_member').exists())
        self.assertTrue(self.member.is_active)

    def test_cannot_add_someone_elses_user(self):
        demo = User.objects.get(username='demo')
        old_gym = demo.userprofile.gym_id

        self.assertEqual(self.add(2, demo.pk).status_code, 400)
        demo.refresh_from_db()
        self.assertEqual(demo.userprofile.gym_id, old_gym)

    def test_cannot_move_gym_staff(self):
        trainer = User.objects.get(username='trainer1')  # added by 'test', but a trainer
        old_gym = trainer.userprofile.gym_id

        self.assertEqual(self.add(2, trainer.pk).status_code, 400)
        trainer.refresh_from_db()
        self.assertEqual(trainer.userprofile.gym_id, old_gym)

    def test_remove_non_member_is_not_found(self):
        self.assertEqual(self.client.delete(self.members_url(1, self.member.pk)).status_code, 404)
