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
[S-005] Our image is built from the `sage` branch, after the tests pass.

Homelab runs this image instead of upstream's, so losing the workflow in an upgrade
would silently put upstream's image (without our changes) back in charge.
"""

# Standard Library
from pathlib import Path
from unittest import TestCase

# Third Party
import yaml


WORKFLOW = Path(__file__).resolve().parents[3] / '.github' / 'workflows' / 'sage-image.yml'
IMAGE = 'ghcr.io/vinneyj/wger-server'


class SageImageWorkflowTestCase(TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(WORKFLOW.read_text())
        # PyYAML reads the bare key `on` as True
        self.triggers = self.workflow.get('on', self.workflow.get(True))
        self.jobs = self.workflow['jobs']

    def test_runs_for_sage(self):
        self.assertEqual(self.triggers['push']['branches'], ['sage'])
        self.assertEqual(self.triggers['pull_request']['branches'], ['sage'])
        self.assertIn('workflow_dispatch', self.triggers)

    def test_tests_run_before_the_build(self):
        steps = ' '.join(str(s.get('run', '')) for s in self.jobs['test']['steps'])
        self.assertIn('manage.py test', steps)
        self.assertEqual(self.jobs['image']['needs'], 'test')

    def test_builds_the_production_image_for_homelab(self):
        steps = self.jobs['image']['steps']
        build = next(s for s in steps if 'build-push-action' in s.get('uses', ''))
        self.assertEqual(build['with']['file'], 'extras/docker/production/Dockerfile')
        self.assertEqual(build['with']['platforms'], 'linux/amd64')
        self.assertIn(f'{IMAGE}:sage-', build['with']['tags'])
        # Pull requests build but never publish
        self.assertIn("github.event_name != 'pull_request'", str(build['with']['push']))

    def test_can_publish_to_the_registry(self):
        self.assertEqual(self.jobs['image']['permissions']['packages'], 'write')
