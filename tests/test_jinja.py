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
import json, pytest
from tests.conftest import *  # imports testing boilerplate
from moto import mock_ssm
from socless.jinja import fromjson, vault, jinja_env, fromtimestamp
from socless.exceptions import SoclessBootstrapError

TEST_SECRET_PATH = "/socless/test/mock_secret"


@pytest.fixture()
def root_obj():
    # setup root_obj for use in tesing TestParamResolver
    return {
        "artifacts": {
            "event": {
                "details": {
                    "firstname": "Sterling",
                    "middlename": "Malory",
                    "lastname": "Archer",
                    "vault_test": "vault:socless_vault_tests.txt",
                    "test_secret": f"{{secret('{TEST_SECRET_PATH}')}}",
                }
            }
        }
    }


def test_raw_function_fromjson():
    mock_json = {"test": "response", "foo": ["bar"], "baz": {"bang": "fizz"}}
    stringified_json = json.dumps(mock_json)
    assert mock_json == fromjson(stringified_json)


def test_raw_function_vault():
    content = vault("socless_vault_tests.txt")
    assert content == "this came from the vault"


def test_jinja_no_timezone_fromtimestamp():
    int_result = fromtimestamp(1633981527)
    string_result = fromtimestamp("1633981527")
    assert int_result == string_result == "2021-10-11T19:45:27+00:00"


def test_jinja_utc_timestamp_fromtimestamp():
    int_result = fromtimestamp(1633981527, "UTC")
    string_result = fromtimestamp("1633981527", "UTC")
    assert int_result == string_result == "2021-10-11T19:45:27+00:00"


def test_jinja_america_los_angeles_fromtimestamp():
    int_result = fromtimestamp(1633981527, "America/Los_Angeles")
    string_result = fromtimestamp("1633981527", "America/Los_Angeles")
    assert int_result == string_result == "2021-10-11T12:45:27-07:00"


def test_jinja_america_new_york_fromtimestamp():
    int_result = fromtimestamp(1633981527, "America/New_York")
    string_result = fromtimestamp("1633981527", "America/New_York")
    assert int_result == string_result == "2021-10-11T15:45:27-04:00"


def test_jinja_america_new_york_fromtimestamp():
    int_result = fromtimestamp(1633981527, "America/New_York")
    string_result = fromtimestamp("1633981527", "America/New_York")
    assert int_result == string_result == "2021-10-11T15:45:27-04:00"


def test_jinja_bad_timestamp_fromtimestamp():
    with pytest.raises(
        SoclessBootstrapError,
        match="^Failed to convert bad_time_stamp to integer. bad_time_stamp is not a valid timestamp. Error:",
    ):
        result = fromtimestamp("bad_time_stamp", "America/New_York")


def test_jinja_bad_timezone_fromtimestamp():
    with pytest.raises(
        SoclessBootstrapError,
        match="^bad/timezone is not a valid timezone name. Error:",
    ):
        result = fromtimestamp("1633981527", "bad/timezone")


def test_jinja_from_string_vault():
    # single quotes are required to escape the . notation for jinja dict accessor
    template = jinja_env.from_string("{{vault('socless_vault_tests.txt')}}")
    content = template.render(context={})
    assert content == "this came from the vault"


@mock_ssm
def test_jinja_secret():
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
    ssm_client.put_parameter(
        Name=TEST_SECRET_PATH,
        Description="A test parameter",
        Value="test_parameter_for_socless",
        Type="SecureString",
    )

    # Using 4 curlies here to properly escape "{{secret('{TEST_SECRET_PATH}')}}"
    template = jinja_env.from_string(f"{{{{secret('{TEST_SECRET_PATH}')}}}}")
    content = template.render(context={})
    assert content == "test_parameter_for_socless"


def test_jinja_from_string_env_var():
    # single quotes are required to escape the . notation for jinja dict accessor
    template = jinja_env.from_string("{{env('AWS_REGION')}}")
    content = template.render(context={})
    assert content == "us-east-1"
