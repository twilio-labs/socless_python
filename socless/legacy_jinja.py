"""Code for the legacy implementation of Jinja in SOCless.

The legacy implementation is currently used by socless_template_string only
to implement string templating feature using a custom Jinja2 single-curly syntax i.e. {context.*}

TODO: This legacy feature should be deprecated when socless_python reaches >v2.0.0
and the implementation should be removed then
"""
from jinja2 import Environment, select_autoescape


# Legacy Jinja Environment Configuration i.e. aka Single Curly
legacy_jinja_env = Environment(
    autoescape=select_autoescape(["html", "xml"]),
    variable_start_string="{",
    variable_end_string="}",
)

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
custom_filters = {"maptostr": maptostr}

# Register Custom Filters
legacy_jinja_env.filters.update(custom_filters)
