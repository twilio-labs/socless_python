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
Code for Jinja2 which Socless uses for templating strings
"""
from jinja2 import Environment, select_autoescape

# Jinja Environment Configuration
jinja_env = Environment(
    autoescape=select_autoescape(['html', 'xml']),
    variable_start_string="{",
    variable_end_string="}")

# Define Custom Filters


def maptostr(target_list):
    """Casts a list of python types to a list of strings
    Args:
        target_list (list): list containing python types
    Returns:
        List containing strings
    """
    return [str(each) for each in target_list]


# Add Custom Filters
custom_filters = {'maptostr': maptostr}

# Register Custom Filters
jinja_env.filters.update(custom_filters)
