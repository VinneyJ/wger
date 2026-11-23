# -*- coding: utf-8 -*-

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

# Standard Library
import os

# Django
from django.urls import path
from django.views.generic import (
    RedirectView,
    TemplateView,
)

# wger
from wger.version import (
    get_version_date,
    get_version_with_git,
)


# AGPL-3.0 §13: users of this modified version must be offered its source.
# Points at the exact deployed commit when the image was built with APP_BUILD_COMMIT.
SOURCE_REPO = 'https://github.com/VinneyJ/wger'
SOURCE_URL = f'{SOURCE_REPO}/tree/{os.environ.get("APP_BUILD_COMMIT") or "sage"}'

urlpatterns = [
    path(
        'code',
        RedirectView.as_view(url=SOURCE_URL),
        name='code',
    ),
    path(
        'about',
        TemplateView.as_view(
            template_name='about.html',
            extra_context={
                'version': get_version_with_git(),
                'date': get_version_date(),
                'source_url': SOURCE_URL,
            },
        ),
        name='about',
    ),
]
