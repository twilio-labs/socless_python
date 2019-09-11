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
from socless.socless import fetch_actual_parameters, fetch_from_vault, socless_save_to_vault, parse_parameters, apply_conversion_from, socless_template_string
import os, boto3


class Test_fetch_actual_parameters(object):

    test_data = {
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

    def test_path_pointing_to_string(self):
        assert fetch_actual_parameters("$.data.string",self.test_data) == self.test_data["data"]["string"]

    def test_path_pointing_to_vault_id(self):
        assert fetch_actual_parameters("$.data.vault_id",self.test_data) == "this came from the vault"

    def test_path_pointing_to_object(self):
        assert fetch_actual_parameters("$.data.object",self.test_data) == self.test_data["data"]["object"]

    def test_with_list_input(self):
        assert fetch_actual_parameters(self.test_data['statics']['list'],self.test_data) == self.test_data['statics']['list']

    def test_with_object_input(self):
        assert fetch_actual_parameters(self.test_data['data']['object'],self.test_data) == self.test_data['data']['object']

    def test_jsonpath_with_json_conversion(self):
        assert fetch_actual_parameters("$.data.string_json!json", self.test_data) == ["hello","world"]

    def test_vault_path_with_json_conversion(self):
        assert fetch_actual_parameters("vault:socless_vault_tests.json!json",self.test_data) == {'hello':'world'}

    def test_json_path_to_vault_path_with_conversion(self):
        assert fetch_actual_parameters("$.data.vault_id_json!json",self.test_data) == {'hello':'world'}

    def test_nested_reference(self):
        assert fetch_actual_parameters(self.test_data['nested_referer']['object'], self.test_data) == {'top_level': 'this_value_is_nested'}


class Test_parse_parameters(object):

    test_data = {
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

    expected_results = {
        "string": test_data['parameters']['test']['string'],
        "path": test_data['artifacts']['event']['text'],
        "vault": "this came from the vault",
        "nested_ref": {
            "nester": test_data['artifacts']['event']['nested']
        }
    }

    def test_case(self):
        assert parse_parameters(self.test_data, None) == self.expected_results



class Test_vault_libraries(object):

    def test_socless_save_to_vault_saves_cotent_correctly(self):
        CONTENT_STRING = "Hello there!"
        result = socless_save_to_vault(CONTENT_STRING)
        s3 = boto3.resource('s3')
        content = s3.Bucket(os.environ['SOCLESS_VAULT']).Object(result['file_id']).get()['Body'].read().decode('utf-8')
        assert content == CONTENT_STRING

    def test_socless_fetch_from_vault(self):
        assert fetch_from_vault('socless_vault_tests.txt') == {"content": "this came from the vault"}

class Test_conversion_libraries(object):

    def test_conversion_from_json(self):
        assert apply_conversion_from('["hello", "world"]',"json") == ['hello', 'world']



class Test_socless_template_string(object):
    """
    Test the socless_template_string function
    """

    context = {
        "safe_string": "Elliot Alderson",
        "unsafe_string": "<script>alert('Elliot Alderson')</script>",
        "dict": {
            "safe_string": "Elliot Alderson",
            "unsafe_string": "<script>alert('Elliot Alderson')</script>"
        },
        "unicodelist": ['hello','world']
    }

    def test_safe_string(self):
        assert socless_template_string("Hello {context.safe_string}",self.context) == "Hello Elliot Alderson"

    def test_unsafe_string(self):
        assert socless_template_string("Hello {context.unsafe_string}",self.context) == "Hello &lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"

    def test_dictionary_reference(self):
        assert socless_template_string("Hello {context.dict}",self.context) == """Hello {'safe_string': 'Elliot Alderson', 'unsafe_string': "&lt;script&gt;alert('Elliot Alderson')&lt;/script&gt;"}"""

    def test_maptostr(self):
        assert socless_template_string("{context.unicodelist|maptostr}",self.context) == "{}".format(['hello','world'])
