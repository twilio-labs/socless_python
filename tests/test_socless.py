# # Copyright 2018 Twilio, Inc.
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License
from moto import mock_s3, mock_dynamodb2
from tests.conftest import s3, dynamodb, setup_vault
import os, boto3, pytest
from socless.socless import fetch_actual_parameters, fetch_from_vault, socless_save_to_vault, parse_parameters, apply_conversion_from, socless_template_string

# initialize test data
TEST_DATA = {
        "data": {
            "string": "value",
            "nested_ref": "this_value_is_nested",
            "vault_id": "vault:socless_vault_tests.txt",
            "vault_id_json": "vault:socless_vault_tests.json",
            "object": {"test": "hello world"},
            "string_json": '["hello","world"]'
        },
        "referencer": {
            "param": "$.data.parameter"
        },
        "statics": {
            'list': ['1','2','3']
        },
        "nested_referer": {
            "object": {
                "top_level": "$.data.nested_ref"
            }
        }
    }

PARSE_TEST_DATA = {
	"_testing": True,
	"this": "test",
	"artifacts": {
		"event": {
			"vault_data": "vault:socless_vault_tests.txt",
			"text": "this is the value at path",
			"nested": "this_value_is_nested"
		}
	},
	"parameters": {
		"test": {
			"string": "hello world",
			"path": "$.artifacts.event.text",
			"vault": "$.artifacts.event.vault_data",
			"nested_ref": {
				"nester": "$.artifacts.event.nested"
			}
		}
	}
}

EXPECTED_RESULTS = {
    "string": PARSE_TEST_DATA['parameters']['test']['string'],
    "path": PARSE_TEST_DATA['artifacts']['event']['text'],
    "vault": "this came from the vault",
    "nested_ref": {
        "nester": PARSE_TEST_DATA['artifacts']['event']['nested']
    }
}

context = {
    "safe_string": "Elliot Alderson",
    "unsafe_string": "<script>alert('Elliot Alderson')</script>",
    "dict": {
        "safe_string": "Elliot Alderson",
        "unsafe_string": "<script>alert('Elliot Alderson')</script>"
    },
    "unicodelist": ['hello','world']
}

def test_path_pointing_to_string():
    assert fetch_actual_parameters("$.data.string",TEST_DATA) == TEST_DATA["data"]["string"]

@mock_s3
def test_path_pointing_to_vault_id(s3):
    setup_vault()
    assert fetch_actual_parameters("$.data.vault_id",TEST_DATA) == "this came from the vault"

def test_path_pointing_to_object():
    assert fetch_actual_parameters("$.data.object",TEST_DATA) == TEST_DATA["data"]["object"]

def test_with_list_input():
    assert fetch_actual_parameters(TEST_DATA['statics']['list'],TEST_DATA) == TEST_DATA['statics']['list']

def test_with_object_input():
    assert fetch_actual_parameters(TEST_DATA['data']['object'],TEST_DATA) == TEST_DATA['data']['object']

def test_jsonpath_with_json_conversion():
    assert fetch_actual_parameters("$.data.string_json!json", TEST_DATA) == ["hello","world"]

@mock_s3
def test_vault_path_with_json_conversion(s3):
    setup_vault()
    assert fetch_actual_parameters("vault:socless_vault_tests.json!json",TEST_DATA) == {'hello':'world'}

@mock_s3
def test_json_path_to_vault_path_with_conversion(s3):
    setup_vault()
    assert fetch_actual_parameters("$.data.vault_id_json!json",TEST_DATA) == {'hello':'world'}

def test_nested_reference():
    assert fetch_actual_parameters(TEST_DATA['nested_referer']['object'], TEST_DATA) == {'top_level': 'this_value_is_nested'}

@mock_s3
def test_parse_parameters():
    setup_vault()
    assert parse_parameters(PARSE_TEST_DATA, None) == EXPECTED_RESULTS

@mock_s3
def test_socless_save_to_vault_saves_cotent_correctly():
    setup_vault()
    CONTENT_STRING = "Hello there!"
    result = socless_save_to_vault(CONTENT_STRING)
    s3 = boto3.resource('s3')
    content = s3.Bucket(os.environ['SOCLESS_VAULT']).Object(result['file_id']).get()['Body'].read().decode('utf-8')
    assert content == CONTENT_STRING

@mock_s3
def test_socless_fetch_from_vault():
    setup_vault()
    assert fetch_from_vault('socless_vault_tests.txt') == {"content": "this came from the vault"}

def test_conversion_from_json():
    assert apply_conversion_from('["hello", "world"]',"json") == ['hello', 'world']

def test_safe_string():
    assert socless_template_string("Hello {context.safe_string}", context) == "Hello Elliot Alderson"

def test_unsafe_string():
    assert socless_template_string("Hello {context.unsafe_string}", context) == "Hello &lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"

def test_dictionary_reference():
    assert socless_template_string("Hello {context.dict}", context) == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "&lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"}"""

def test_maptostr():
    assert socless_template_string("{context.unicodelist|maptostr}", context) == "{}".format(['hello','world'])
