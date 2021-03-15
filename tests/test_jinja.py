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
from socless.jinja import fromjson, vault, jinja_env

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


def test_jinja_from_string_vault():
    # single quotes are required to escape the . notation for jinja dict accessor
    template = jinja_env.from_string("{vault('socless_vault_tests.txt')}")
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

    template = jinja_env.from_string(f"{{secret('{TEST_SECRET_PATH}')}}")
    content = template.render(context={})
    assert content == "test_parameter_for_socless"


def test_jinja_from_string_env_var():
    # single quotes are required to escape the . notation for jinja dict accessor
    template = jinja_env.from_string("{env('AWS_REGION')}")
    content = template.render(context={})
    assert content == "us-east-1"

