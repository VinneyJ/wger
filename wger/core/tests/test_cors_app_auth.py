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
[S-004] Browser apps on another domain can use the app sign-in API.

The app endpoints (`/allauth/app/`) use tokens, not cookies, so allowing any origin
is as safe as it already is for `/api/`. Cookie-based pages, like the web login,
stay same-origin.
"""

# Django
from django.test import TestCase


ORIGIN = 'https://app.example.com'


class CorsAppAuthTestCase(TestCase):
    def preflight(self, path, headers='content-type'):
        return self.client.options(
            path,
            HTTP_ORIGIN=ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
        )

    def test_app_login_preflight_allowed(self):
        response = self.preflight('/allauth/app/v1/auth/login', 'content-type,x-session-token')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('access-control-allow-origin'), '*')
        allowed = response.headers.get('access-control-allow-headers', '').lower()
        self.assertIn('x-session-token', allowed)  # sent by the two-factor step
        self.assertIn('authorization', allowed)

    def test_app_login_answer_carries_cors_header(self):
        response = self.client.post(
            '/allauth/app/v1/auth/login',
            {'username': 'nobody', 'password': 'wrong'},
            content_type='application/json',
            HTTP_ORIGIN=ORIGIN,
        )
        self.assertEqual(response.headers.get('access-control-allow-origin'), '*')

    def test_api_still_allowed(self):
        self.assertEqual(self.preflight('/api/v2/').headers.get('access-control-allow-origin'), '*')

    def test_cookie_login_stays_same_origin(self):
        response = self.preflight('/en/user/login')
        self.assertIsNone(response.headers.get('access-control-allow-origin'))
