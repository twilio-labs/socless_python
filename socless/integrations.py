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
Classes and modules for Integrations
"""
import boto3, simplejson as json, os
from .logger import socless_log
from .vault import fetch_from_vault

VAULT_TOKEN = "vault:"
PATH_TOKEN = "$."
CONVERSION_TOKEN = "!"


class ParameterResolver:
    """Evaluates parameter references for integrations
    """

    def __init__(self,root_obj):
        self.root_obj = root_obj


    def resolve_jsonpath(self, path):
        """Resolves a JsonPath reference to the actual value referenced.
        Does not support the full JsonPath specification

        Args:
            reference: The JsonPath reference e.g. $.artifacts.investigation_id
        Returns:
            The referenced element. May be any Python built-in type
        """
        pre, sep, post = path.partition(PATH_TOKEN)
        keys = post.split('.')
        obj_copy = self.root_obj.copy()
        for key in keys:
            value = obj_copy.get(key)
            if isinstance(value,str) and value.startswith(VAULT_TOKEN):
                actual = self.resolve_vault_path(value)
            else:
                actual = value
            obj_copy = actual
        return obj_copy

    def resolve_vault_path(self, path):
        """Resolves a vault reference to the actual vault file content

        This handles vault references e.g `vault:file_name` that are passed
        in as parameters to Socless integrations. It fetches and returns the content
        of the Vault object with name `file_name` in the vault.

        Args:
            path (str): The vault reference
        Returns:
            str: The content of the referenced Vault object
        """
        _, __, file_id = path.partition(VAULT_TOKEN)
        data = fetch_from_vault(file_id,content_only=True)
        return data

    def resolve_reference(self, reference_path):
        """Evaluate a reference path and return the referenced value

        Args:
            reference_path: The reference to evaluate may be any Python
                built-in type
        Returns:
            The resulting value. May be any Python built-in type
        """

        if not isinstance(reference_path, str):
            if isinstance(reference_path, dict):
                resolved_dict = {}
                for key, value in list(reference_path.items()):
                    resolved_dict[key] = self.resolve_reference(value)
                return resolved_dict
            else:
                return reference_path

        if not (reference_path.startswith(VAULT_TOKEN) or reference_path.startswith(PATH_TOKEN)):
            return reference_path

        reference, _ , conversion = reference_path.partition(CONVERSION_TOKEN)

        if reference.startswith(PATH_TOKEN):
            resolved =  self.resolve_jsonpath(reference)
        elif reference.startswith(VAULT_TOKEN):
            resolved =  self.resolve_vault_path(reference)

        if conversion:
            resolved = self.apply_conversion_from(resolved,conversion)
        return resolved

    def resolve_parameters(self, parameters):
        """Resolve a set of parameter references to their actual vaules

        Args:
            parameters (dict): Parameter references to resolve
        Returns:
            a dictionary containing resolved parameter references
        """
        actual_params = {}
        for parameter, reference in list(parameters.items()):
            actual_params[parameter] = self.resolve_reference(reference)
        return actual_params

    def apply_conversion_from(self,data,conversion):
        """Convert the data type of a parameter

        Handles conversion of the datatype of a parameter intended for an integration

        Args:
            data (str): The data to convert
            conversion (str): The conversion to apply
        Returns:
            str: The converted data
        """
        if conversion == "json":
            return json.loads(data)

class ExecutionContext:
    """The execution context object
    """

    def __init__(self,execution_id):
        self.execution_id = execution_id

    def fetch_context(self):
        """Fetch execution context from the Execution Results table

        Args:
            execution_id (str): The execution id for a playbook execution instance
        Returns:
            dict: The execution result object
        """
        RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
        results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)
        item_resp = results_table.get_item(Key={
            'execution_id': self.execution_id
        },ConsistentRead=True)
        item = item_resp.get("Item",{})
        if not item:
            raise Exception("Error: Unable to get execution_id {} from {}".format(self.execution_id, RESULTS_TABLE))
        return item

    def save_state_results(self,state_name,result, errors={}):
        """Save the results of a State's execution to the Execution results table
        Args:
            state_name (str): The name of the state
            result (obj): The result to save
        """
        RESULTS_TABLE = os.environ.get('SOCLESS_RESULTS_TABLE')
        results_table = boto3.resource('dynamodb').Table(RESULTS_TABLE)

        error_expression = ""
        expression_attributes = {':r': result}
        if errors:
            error_expression = ",#results.errors = :e"
            expression_attributes[':e'] = errors

        results_table.update_item(
            Key={
                "execution_id": self.execution_id
            },
            UpdateExpression=f'SET #results.#results.#name = :r, #results.#results.#last_results = :r {error_expression}',
            ExpressionAttributeValues=expression_attributes,
            ExpressionAttributeNames={
                "#results": "results",
                "#name": state_name,
                "#last_results": '_Last_Saved_Results'
            }
        )

class StateHandler:
    """Controls the execution of an integration for a given state in a Playbook
    """

    def __init__(self,event,lambda_context,integration_handler,include_event=False):
        """
        Args:
            event (dict): The input passed to the Lambda function by the service that triggered it
            lambda_context (obj): The Lambda context object
            integration_handler (func): The function that implements the integrations business logic
            include_playbook_context (bool): Set to `True` to make the full context object of the executing playbook available to the integration
        """
        #TODO: Figure out how to handle include_event
        self.event = event
        self.testing = bool(event.get('_testing'))
        try:
            self.state_config = event['State_Config']
        except:
            raise KeyError("No State_Config was passed to the integration")

        try:
            self.state_name = self.state_config['Name']
        except:
            raise KeyError("`Name` not set in State_Config")

        try:
            self.state_parameters = self.state_config['Parameters']
        except:
            raise KeyError("`Parameters` not set in State_Config")

        self.execution_id = event.get('execution_id','')
        if self.testing:
            self.context = event
        else:
            if self.execution_id:
                self.execution_context = ExecutionContext(self.execution_id)
                self.context = self.execution_context.fetch_context()['results']
                self.context['execution_id'] = self.execution_id
                if 'errors' in event:
                    self.context['errors'] = event['errors']
            else:
                raise Exception("Execution id not found in non-testing context")

        self.integration_handler = integration_handler
        self.include_event = include_event
        #TODO: Find a way to maintain the execution_id between lambdas

    def execute(self):
        """Execute the integration to fulfil the assigned state
        """
        resolver = ParameterResolver(self.context)
        actual_params = resolver.resolve_parameters(self.state_parameters)
        if self.include_event:
            result = self.integration_handler(self.context,**actual_params)
        else:
            result = self.integration_handler(**actual_params)

        if not isinstance(result, dict):
            raise Exception("Result returned from the integration handler is not a Python dictionary. Must be a Python dictionary")

        if not self.testing:
            if 'errors' not in self.context:
                self.context['errors'] = {}
            self.execution_context.save_state_results(self.state_name,result, errors=self.context['errors'])
        return result
