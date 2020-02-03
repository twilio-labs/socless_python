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
from tests.conftest import * #imports testing boilerplate
from .helpers import MockLambdaContext, dict_to_item
import json, os
from copy import deepcopy
import pytest
from moto import mock_stepfunctions, mock_sts, mock_iam

from socless.logger import socless_log, socless_log_then_raise


bucket_name = os.environ['SOCLESS_VAULT']

def test_socless_log_then_raise():
    with pytest.raises(Exception):
        socless_log_then_raise('testing error')

def test_socless_log_then_raise_fails_on_empty_message():
    with pytest.raises(ValueError):
        socless_log_then_raise('')

def test_socless_log_then_raise_fails_on_extra_not_being_dict():
    with pytest.raises(ValueError):
        socless_log_then_raise('test_message', [])

def test_socless_log_error(capfd):
    level = "ERROR"
    response = socless_log.error("Testing")
    
    # Read logging and convert to dict for assertion
    out, err = capfd.readouterr()
    json_out = json.loads(out)
    assert json_out['context']['level'] == level
    assert json_out['body']['message'] == "Testing"

def test_socless_log_info(capfd):
    level = "INFO"
    response = socless_log.info("Testing")
    
    # Read logging and convert to dict for assertion
    out, err = capfd.readouterr()
    json_out = json.loads(out)
    assert json_out['context']['level'] == level
    assert json_out['body']['message'] == "Testing"

def test_socless_log_warn(capfd):
    level = "WARN"
    response = socless_log.warn("Testing")
    
    # Read logging and convert to dict for assertion
    out, err = capfd.readouterr()
    json_out = json.loads(out)
    assert json_out['context']['level'] == level
    assert json_out['body']['message'] == "Testing"

def test_socless_log_critical(capfd):
    level = "CRITICAL"
    response = socless_log.critical("Testing")
    
    # Read logging and convert to dict for assertion
    out, err = capfd.readouterr()
    json_out = json.loads(out)
    assert json_out['context']['level'] == level
    assert json_out['body']['message'] == "Testing"

def test_socless_log_debug(capfd):
    level = "DEBUG"
    response = socless_log.debug("Testing")
    
    # Read logging and convert to dict for assertion
    out, err = capfd.readouterr()
    json_out = json.loads(out)
    assert json_out['context']['level'] == level
    assert json_out['body']['message'] == "Testing"
