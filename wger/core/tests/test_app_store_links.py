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
from django.test import override_settings
from django.urls import reverse

# wger
from wger.core.tests.base_testcase import WgerTestCase


class AppStoreLinksTestCase(WgerTestCase):
    """
    Test that WGER_SHOW_APP_STORE_LINKS controls the app store badges on the About page
    """

    stores = (
        'play.google.com',
        'apps.apple.com',
        'flathub.org',
    )

    def test_about_page_shows_the_badges_by_default(self):
        response = self.client.get(reverse('software:about'))

        for store in self.stores:
            self.assertContains(response, store)

    @override_settings(WGER_SHOW_APP_STORE_LINKS=False)
    def test_about_page_badges_can_be_hidden(self):
        response = self.client.get(reverse('software:about'))

        for store in self.stores:
            self.assertNotContains(response, store)

    def test_footer_has_no_badges(self):
        response = self.client.get(reverse('core:user:login'))

        for store in self.stores:
            self.assertNotContains(response, store)
