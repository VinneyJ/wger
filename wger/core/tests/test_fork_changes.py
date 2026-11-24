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
Checks that the changes listed in FORK-CHANGES.md survive upstream upgrades.

These fail loudly when an upgrade brings back something we removed, or when the
list itself is out of shape.
"""

# Standard Library
import re
from pathlib import Path

# Django
from django.urls import (
    NoReverseMatch,
    reverse,
)

# wger
from wger.core.tests.base_testcase import WgerTestCase


REPO_ROOT = Path(__file__).resolve().parents[3]
CHANGES_FILE = REPO_ROOT / 'FORK-CHANGES.md'
ROW = re.compile(r'^\| (S-\d{3}) \|(.+)$')
STATUS = re.compile(r'^(Active|Pending \(PR #\d+\)|Upstreamed \(wger [\w.]+\)|Dropped.*)$')


def change_rows():
    """The rows of the table in FORK-CHANGES.md, as dicts"""
    rows = []
    for line in CHANGES_FILE.read_text().splitlines():
        match = ROW.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(
            {
                'id': cells[0],
                'status': cells[2],
                'guards': re.findall(r'`([^`]+\.py)`', cells[4]),
            }
        )
    return rows


class ForkChangesFileTestCase(WgerTestCase):
    """S-003: the list of fork changes stays usable"""

    def test_file_exists_and_has_rows(self):
        self.assertTrue(CHANGES_FILE.exists())
        self.assertGreaterEqual(len(change_rows()), 1)

    def test_ids_are_unique(self):
        ids = [row['id'] for row in change_rows()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_statuses_are_known(self):
        for row in change_rows():
            with self.subTest(change=row['id']):
                self.assertRegex(row['status'], STATUS)

    def test_active_changes_have_existing_guard_tests(self):
        for row in change_rows():
            if row['status'] != 'Active':
                continue
            with self.subTest(change=row['id']):
                self.assertTrue(row['guards'], 'Active changes need at least one guard test')
                for guard in row['guards']:
                    self.assertTrue((REPO_ROOT / guard).exists(), f'{guard} is missing')


class RemovedPagesStayRemovedTestCase(WgerTestCase):
    """S-001: pages we removed must not come back with an upgrade"""

    removed_routes = (
        'software:features',
        'software:about-us',
        'software:api',
        'software:tos',
        'core:imprint',
    )

    def test_routes_are_gone(self):
        for name in self.removed_routes:
            with self.subTest(route=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)

    def test_menu_has_no_about_this_software_or_translate_link(self):
        self.user_login('test')
        response = self.client.get(reverse('core:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'About this software')
        self.assertNotContains(response, 'hosted.weblate.org')
