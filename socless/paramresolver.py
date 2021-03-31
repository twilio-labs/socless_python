"""
SOCless Parameter Resolver Implementation
"""
from typing import Any
from .logger import socless_log
from .exceptions import SoclessException, SoclessBootstrapError
from .jinja import render_jinja_from_string
from jinja2.exceptions import TemplateSyntaxError, UndefinedError


VAULT_TOKEN = "vault:"
PATH_TOKEN = "$."
CONVERSION_TOKEN = "!"


class ParameterResolver:
    """Evaluates parameter references for integrations"""

    def __init__(self, root_obj):
        self.root_obj = root_obj

    def resolve_reference(self, reference_path):
        """Evaluate a reference path and return the referenced value
        Args:
            reference_path: The reference to evaluate may be any Python
                built-in type
        Returns:
            The resulting value. May be any Python built-in type
        """

        if isinstance(reference_path, str):
            return resolve_string_parameter(reference_path, self.root_obj)
        elif isinstance(reference_path, dict):
            resolved_dict = {}
            for key, value in list(reference_path.items()):
                resolved_dict[key] = self.resolve_reference(value)
            return resolved_dict
        elif isinstance(reference_path, list):
            resolved_list = []
            for item in reference_path:
                resolved_list.append(self.resolve_reference(item))
            return resolved_list
        else:
            return reference_path

    def resolve_parameters(self, parameters):
        """Resolve a set of parameter references to their actual vaules
        Args:
            parameters (dict): Parameter references to resolve
        Returns:
            a dictionary containing resolved parameter references
        """
        actual_params = {}
        for parameter, reference in parameters.items():
            actual_params[parameter] = self.resolve_reference(reference)
        return actual_params


def add_brackets_and_conditionally_add_fromjson(
    template: str, should_add_fromjson: bool
):
    if should_add_fromjson:
        template = template + " |fromjson"
    return "{{" + template + "}}"


def convert_deprecated_vault_to_template(vault_reference) -> str:
    reference, _, conversion = vault_reference.partition(CONVERSION_TOKEN)
    _, _, file_id = reference.partition(VAULT_TOKEN)
    template = f"vault('{file_id}')"
    return add_brackets_and_conditionally_add_fromjson(template, bool(conversion))


def convert_legacy_reference_to_template(reference_path: str) -> str:
    """Allow backwards compatibility for legacy socless parameter reference to jinja templates.
    `render_jinja_template` jinja translation is supported by this function that converts
    legacy references to valid jinja templates according to the table below:

        Legacy Reference   | Converted Jinja template
        ----------------   | ------------------------
        “$.<ref_path>”     |  “{context.<ref_path>}”
        “vault:<vault-id>” |  “{vault-id | fromvault}”
        "<something>!json" |  "{<something> | fromjson}"
    """
    try:
        # modify template if it starts with `$.` or `vault:`
        if reference_path.startswith(PATH_TOKEN):
            _, _, conversion_check = reference_path.partition(CONVERSION_TOKEN)
            jinja_dict_referencing = f"context{reference_path[1:]}"
            return add_brackets_and_conditionally_add_fromjson(
                jinja_dict_referencing, bool(conversion_check)
            )
        elif reference_path.startswith(VAULT_TOKEN):
            return convert_deprecated_vault_to_template(reference_path)

        return reference_path
    except (TypeError, KeyError) as e:
        raise SoclessException(
            f"Unable to convert reference type {type(reference_path)} to template - {e}"
        )


def resolve_string_parameter(parameter: str, root_object: dict) -> Any:
    template = convert_legacy_reference_to_template(parameter)
    try:
        resolved = render_jinja_from_string(template, root_object)
        if isinstance(resolved, str):
            # if jsonpath renders into something with a vault_token, it needs to run through jinja again
            if resolved.startswith(VAULT_TOKEN):
                new_template_string = convert_deprecated_vault_to_template(resolved)
                return render_jinja_from_string(new_template_string, root_object)

            ## autoescaping is currently disabled, this line may not be necessary
            # resolved = resolved.replace("&#34;", '"').replace("&#39;", "'")
    except TemplateSyntaxError as e:
        socless_log.warn(
            f"Invalid jinja Template Syntax error {e} | for template: {template}"
        )
        return template
    except UndefinedError as e:
        raise SoclessBootstrapError(
            f"Undefined variable when resolving parameter: {parameter} template {e} | for template: {template}"
        )
    return resolved
