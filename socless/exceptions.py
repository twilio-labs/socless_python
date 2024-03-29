# Copyright 2018 Twilio, Inc
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

"""
Socless Exception classes
"""


class SoclessException(Exception):
    pass


class SoclessNotFoundError(Exception):
    pass


class SoclessEventsError(Exception):
    pass


class SoclessBootstrapError(Exception):
    pass


class SoclessVaultError(SoclessException):
    """Errors geenrated by SOCless vault.py interactions"""

    pass
