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
from socless.utils import gen_id, gen_datetimenow
import unittest


def test_gen_datetimenow():
    """Testing the gen_datetimenow util"""
    response = gen_datetimenow()
    assert type(response) == str
    assert response.endswith('Z')


def test_gen_id():
    """Testing the gen_id util"""
    response = gen_id(8)
    assert len(response) == 8
    assert type(response) == str
