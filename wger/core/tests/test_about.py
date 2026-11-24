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

# Django
from django.urls import reverse

# wger
from wger.core.tests.base_testcase import WgerTestCase
from wger.software.urls import SOURCE_REPO


class AboutPageTestCase(WgerTestCase):
    """
    The AGPL source offer and data attribution must stay reachable
    """

    def test_about_page(self):
        response = self.client.get(reverse('software:about'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'agpl-3.0')
        self.assertContains(response, SOURCE_REPO)
        self.assertContains(response, 'Open Food Facts')
        self.assertContains(response, 'by-sa')

    def test_footer_links(self):
        response = self.client.get(reverse('core:user:login'))

        self.assertContains(response, reverse('software:about'))
        self.assertContains(response, reverse('software:code'))

    def test_source_code_redirect(self):
        response = self.client.get(reverse('software:code'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(SOURCE_REPO + '/tree/'))

    def test_anonymous_index_goes_to_login(self):
        response = self.client.get(reverse('core:index'))

        self.assertRedirects(response, reverse('core:user:login'), fetch_redirect_response=False)
