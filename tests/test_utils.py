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
from socless.utils import gen_id, gen_datetimenow, convert_empty_strings_to_none
import unittest
from copy import deepcopy


def test_gen_datetimenow():
    """Testing the gen_datetimenow util"""
    response = gen_datetimenow()
    assert type(response) == str
    assert response.endswith("Z")


def test_gen_id():
    """Testing the gen_id util"""
    response = gen_id(8)
    assert len(response) == 8
    assert type(response) == str


def test_convert_empty_strings_to_none():
    """Testing the convert_empty_strings_to_none util"""

    testDict = {
        "errors": {
            "Await_Reverify_Ticket_Type": {"Error": "States.Timeout", "Cause": ""},
            "TEST_List": [],
            "TEST_nested_list_empty_dict": [{"var1": "", "var2": {}}],
            "TEST_decimals": 1.5,
        }
    }

    expected_output = deepcopy(testDict)
    expected_output["errors"]["Await_Reverify_Ticket_Type"]["Cause"] = None
    expected_output["errors"]["TEST_nested_list_empty_dict"][0]["var1"] = None

    assert convert_empty_strings_to_none(testDict) == expected_output
