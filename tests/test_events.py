# Copyright 2018 Twilio, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
from .helpers import MockLambdaContext
from moto import mock_dynamodb2
from tests.conftest import setup_tables, dynamodb
import boto3, os

import responses # because moto breaks requests
responses.add_passthru('https://')# moto+requests needs this
responses.add_passthru('http://')# 



@mock_dynamodb2
def test_create_events(dynamodb):
    from socless.events import create_events
    event = {
        "event_type": "ParamsToStateMachineTester",
        "details": [
            {"username": "ubalogun","type": "user","id":"1"},
            {"username": "ubalogun","type": "user","id":"2"},
            {"username": "ubalogun","type": "user","id":"1"}
        ],
        "playbook": "ParamsToStateMachineTester",
        "dedup_keys": ["username", "id"]
    }

    #setup tables
    boto3.setup_default_session()
    setup_tables()

    assert create_events(event,MockLambdaContext())['status'] == True
