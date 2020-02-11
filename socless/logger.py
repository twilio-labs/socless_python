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
Logging library
"""
from datetime import datetime
import os
import inspect
import simplejson as json


class socless_log:
    ERROR = 'ERROR'
    INFO = 'INFO'
    WARN = WARNING = 'WARN'
    DEBUG = 'DEBUG'
    CRITICAL = 'CRITICAL'

    @classmethod
    def __log(cls, level, message, extra={}):
        """
        Writes a log message
        """
        if not message:
            raise ValueError("Message must be provided")

        if not isinstance(extra, dict):
            raise ValueError("Extra must be a dictionary")
        payload = {
            "context": {
                "time": "{}Z".format(datetime.utcnow().isoformat()),
                "aws_region": os.environ.get('AWS_REGION', ''),
                "function_name": os.environ.get('AWS_LAMBDA_FUNCTION_NAME', ''),
                "execution_env": os.environ.get('AWS_EXECUTION_ENV', ''),
                "memory_size": os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', ''),
                "function_version": os.environ.get('AWS_LAMBDA_FUNCTION_VERSION', ''),
                "function_log_group": os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', ''),
                "source": "Socless",
                "level": level,
                "lineno": inspect.currentframe().f_back.f_back.f_lineno
            },
            "body": {
                "message": message,
                "extra": extra
            }
        }
        return json.dumps(payload)

    @classmethod
    def info(self, message, extra={}):
        """
        Write a log message with level info
        """
        print((self.__log(self.INFO, message, extra)))

    @classmethod
    def error(self, message, extra={}):
        """
        Write an error message
        """
        print((self.__log(self.ERROR, message, extra)))

    @classmethod
    def debug(self, message, extra={}):
        """
        Write a debug message
        """
        print((self.__log(self.DEBUG, message, extra)))

    @classmethod
    def critical(self, message, extra={}):
        """
        Write a critical message
        """
        print((self.__log(self.CRITICAL, message, extra)))

    @classmethod
    def warn(self, message, extra={}):
        """
        Write a warning message
        """
        print((self.__log(self.WARN, message, extra)))


def socless_log_then_raise(error_string, extras={}):
    """Log an error then raise an exception
    Args:
        error_string (str): The error message to log and raise
        extras (dict): Additional key value pairs to log
    Raises:
        Exception - Only raises the standard `Exception` error
    """
    socless_log.error(error_string, extras)
    raise Exception(error_string)
