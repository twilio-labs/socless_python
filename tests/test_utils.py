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
from os import replace
from socless.utils import (
    gen_id,
    gen_datetimenow,
    convert_empty_strings_to_none,
    replace_decimals,
    replace_floats_with_decimals,
)
from copy import deepcopy
from decimal import Decimal


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


def test_replace_decimals():

    int_one = replace_decimals(Decimal("1"))
    float_one = replace_decimals(Decimal("1.0"))

    # Because 1.0 == 1 in Python, we also have to assert the correct type is returned
    assert int_one == 1 and isinstance(int_one, int)
    assert float_one == 1.0 and isinstance(float_one, float)

    assert replace_decimals([1, Decimal("1")]) == [1, 1]
    assert replace_decimals(
        {
            "int": 1,
            "float": 1.0,
            "bool": True,
            "string": "hello",
            "list": [1, Decimal("1")],
            "decimal": Decimal("1.0"),
            "nested_dict": {"decimal": Decimal("1")},
        }
    ) == {
        "int": 1,
        "float": 1.0,
        "bool": True,
        "string": "hello",
        "list": [1, 1],
        "decimal": 1.0,
        "nested_dict": {"decimal": 1},
    }


def test_replace_floats_with_decimals():
    assert replace_floats_with_decimals(1.0) == Decimal("1.0")
    assert replace_floats_with_decimals(
        {
            "int": 1,
            "float": 1.0,
            "list": [1, 1.0],
            "dict": {"int": 1, "float": 1.0},
        }
    ) == {
        "int": 1,
        "float": Decimal("1.0"),
        "list": [1, Decimal("1.0")],
        "dict": {"int": 1, "float": Decimal("1.0")},
    }
