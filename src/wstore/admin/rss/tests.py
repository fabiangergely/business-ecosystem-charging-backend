# -*- coding: utf-8 -*-

# Copyright (c) 2013 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of WStore.

# WStore is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL)
# as published by the European Commission, either version 1.1
# of the License, or (at your option) any later version.

# WStore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.

# You should have received a copy of the European Union Public Licence
# along with WStore.
# If not, see <https://joinup.ec.europa.eu/software/page/eupl/licence-eupl>.

import json
import types
from mock import MagicMock
from nose_parameterized import parameterized
from urllib2 import HTTPError

from django.test import TestCase
from django.test.client import RequestFactory
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from wstore.models import RSS, Context
from wstore.store_commons.utils.testing import decorator_mock, build_response_mock, decorator_mock_callable


class ExpenditureMock():

    _refresh = False

    def ExpenditureManager(self, rss, cred):
        # build object
        return self.ExpAux(self)

    class ExpAux():
        def __init__(self, classCont):
            self._context = classCont

        def set_provider_limit(self):
            if not self._context._refresh:
                self._context._refresh = True
                raise HTTPError('http://rss.test.com', 401, 'Unauthorized', None, None)


class RSSViewTestCase(TestCase):

    tags = ('rss-view')

    @classmethod
    def setUpClass(cls):
        from wstore.store_commons.utils import http
        # Save the reference of the decorators
        cls._old_auth = types.FunctionType(
            http.authentication_required.func_code,
            http.authentication_required.func_globals, 
            name = http.authentication_required.func_name,
            argdefs = http.authentication_required.func_defaults,
            closure = http.authentication_required.func_closure
        )

        cls._old_supp = types.FunctionType(
            http.supported_request_mime_types.func_code,
            http.supported_request_mime_types.func_globals, 
            name = http.supported_request_mime_types.func_name,
            argdefs = http.supported_request_mime_types.func_defaults,
            closure = http.supported_request_mime_types.func_closure
        )

        # Mock class decorators
        http.authentication_required = decorator_mock
        http.supported_request_mime_types = decorator_mock_callable

        from wstore.admin.rss import views
        cls.views = views
        cls.views.build_response = build_response_mock
        super(RSSViewTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Restore mocked decorators
        from wstore.store_commons.utils import http
        http.authentication_required = cls._old_auth
        http.supported_request_mime_types = cls._old_supp
        super(RSSViewTestCase, cls).tearDownClass()

    def setUp(self):
        # Create user mock
        self.user = MagicMock()
        self.user.userprofile = MagicMock()
        self.user.userprofile.access_token = 'accesstoken'
        self.user.userprofile.refresh_token = 'refreshtoken'
        self.user.is_staff = True

        # Create request mock
        self.request = MagicMock()
        self.request.user = self.user

        # Create context mock
        self.cont_instance = MagicMock()
        self.cont_instance.allowed_currencies = {
            'default': 'EUR',
            'allowed': [{
                'currency': 'EUR'
            }]
        }
        self.cont_instance.is_valid_currency.return_value = True
        self.views.Context = MagicMock()
        self.views.Context.objects = MagicMock()
        self.views.Context.objects.all.return_value = [self.cont_instance]

        # Create RSS mock
        self.rss_object = MagicMock()
        self.views.RSS = MagicMock()
        self.views.RSS.objects = MagicMock()
        self.views.RSS.objects.create.return_value = self.rss_object
        self.views.RSS.objects.get.return_value = self.rss_object
        self.views.RSS.objects.delete = MagicMock()
        self.views.RSS.objects.filter.return_value = []

        from django.conf import settings
        settings.OILAUTH = True

    # Different side effects that can occur
    def _revoke_staff(self):
        self.user.is_staff = False

    def _existing_rss(self):
        self.views.RSS.objects.filter.return_value = [self.rss_object]

    def _invalid_currencies(self):
        self.cont_instance.is_valid_currency.return_value = False

    def _unauthorized(self):
        set_mock = MagicMock()
        set_mock.set_provider_limit.side_effect = HTTPError('http://rss.test.com', 401, 'Unauthorized', None, None)
        self.views.ExpenditureManager = MagicMock()
        self.views.ExpenditureManager.return_value = set_mock

    def _manager_failure(self):
        set_mock = MagicMock()
        set_mock.set_provider_limit.side_effect = Exception('Failure')
        self.views.ExpenditureManager = MagicMock()
        self.views.ExpenditureManager.return_value = set_mock

    def _rss_failure(self):
        set_mock = MagicMock()
        set_mock.set_provider_limit.side_effect = HTTPError('http://rss.test.com', 500, 'Unauthorized', None, None)
        self.views.ExpenditureManager = MagicMock()
        self.views.ExpenditureManager.return_value = set_mock

    @parameterized.expand([
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (201, 'Created', 'correct'), True, {
        'currency': 'EUR',
        'perTransaction':10000,
        'weekly': 100000,
        'daily': 10000,
        'monthly': 100000
    }),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/',
        'limits': {
            'currency': 'EUR',
            'perTransaction': '10000',
            'daily': '10000',
            'weekly': '10000',
            'monthly': '10000'
        }
    }, True, (201, 'Created', 'correct'), True, {
        'currency': 'EUR',
        'perTransaction':10000.0,
        'weekly': 10000.0,
        'daily': 10000.0,
        'monthly': 10000.0
    }),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/',
        'limits': {
            'currency': 'EUR'
        }
    }, False, (201, 'Created', 'correct'), True, {
        'currency': 'EUR',
        'perTransaction':10000,
        'weekly': 100000,
        'daily': 10000,
        'monthly': 100000
    }),
    ({
        'limits': {
            'currency': 'EUR'
        }
    }, False, (400, 'Invalid JSON content', 'error'), False, {}),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (403, 'Forbidden', 'error'), False, {}, _revoke_staff),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (400, 'Invalid JSON content', 'error'), False, {}, _existing_rss),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/',
        'limits': {
            'currency': 'euro'
        }
    }, False, (400, 'Invalid currency', 'error'), False, {}, _invalid_currencies),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (401, "You don't have access to the RSS instance requested", 'error'), False, {}, _unauthorized),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (400, 'Failure', 'error'), False, {}, _manager_failure),
    ({
        'name': 'testrss',
        'host': 'http://rss.test.com/'
    }, False, (502, 'The RSS has failed creating the expenditure limits', 'error'), False, {}, _rss_failure),
    ])
    def test_rss_creation(self, data, refresh, resp, created, expected_request, side_effect=None):

        # Include data to mock
        self.request.raw_post_data = json.dumps(data)

        # Mock ExpenditureManager
        self.views.ExpenditureManager = MagicMock()

        # Create a mock method to manage the token refresh
        # if needed
        if refresh:
            exp_mock = ExpenditureMock()
            self.views.ExpenditureManager = exp_mock.ExpenditureManager
            # Create social auth mocks
            social_mock = MagicMock()
            filter_mock = MagicMock()
            object_mock = MagicMock()
            object_mock.extra_data = {
                'access_token': 'accesstoken',
                'refresh_token': 'refreshtoken'
            }
            filter_mock.return_value = [object_mock]
            social_mock.filter = filter_mock
            self.request.user.social_auth = social_mock

        # Create the corresponding side effect if needed
        if side_effect:
            side_effect(self)

        # Call the view
        collection = self.views.RSSCollection(permitted_methods=('GET', 'POST'))
        response = collection.create(self.request)

        # Check response
        val = json.loads(response.content)
        self.assertEquals(response.status_code, resp[0])
        self.assertEquals(val['message'], resp[1])
        self.assertEquals(val['result'], resp[2])

        # Check the result depending if the model should
        # have been created
        if created:
            # Check rss call
            self.views.RSS.objects.create.assert_called_with(name=data['name'], host=data['host'], expenditure_limits=expected_request)
            self.assertEquals(self.rss_object.access_token, self.user.userprofile.access_token)
        else:
            self.views.RSS.objects.delete.assert_called_once()
