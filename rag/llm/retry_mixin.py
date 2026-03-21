#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import functools
import logging
import os
import random
import time
from strenum import StrEnum


class LLMErrorCode(StrEnum):
    ERROR_RATE_LIMIT = "RATE_LIMIT_EXCEEDED"
    ERROR_AUTHENTICATION = "AUTH_ERROR"
    ERROR_INVALID_REQUEST = "INVALID_REQUEST"
    ERROR_SERVER = "SERVER_ERROR"
    ERROR_TIMEOUT = "TIMEOUT"
    ERROR_CONNECTION = "CONNECTION_ERROR"
    ERROR_MODEL = "MODEL_ERROR"
    ERROR_MAX_ROUNDS = "ERROR_MAX_ROUNDS"
    ERROR_CONTENT_FILTER = "CONTENT_FILTERED"
    ERROR_QUOTA = "QUOTA_EXCEEDED"
    ERROR_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
    ERROR_GENERIC = "GENERIC_ERROR"


def is_retryable(error):
    """Return True if the exception is a transient/retryable error.
    Matches the old _should_retry logic: only RATE_LIMIT and SERVER errors.
    """
    msg = str(error).lower()
    for signals in (
        ("rate limit", "429", "tpm limit", "too many requests"),
        ("503", "502", "504", "500", "unavailable"),
    ):
        if any(s in msg for s in signals):
            return True
    return False


def classify_error(error):
    """Classify an exception into an LLMErrorCode for detailed error messages."""
    msg = str(error).lower()
    for signals, code in (
        (["quota", "capacity", "credit", "billing", "balance", "欠费"], LLMErrorCode.ERROR_QUOTA),
        (["rate limit", "429", "tpm limit", "too many requests", "requests per minute"], LLMErrorCode.ERROR_RATE_LIMIT),
        (["auth", "key", "apikey", "401", "forbidden", "permission"], LLMErrorCode.ERROR_AUTHENTICATION),
        (["invalid", "bad request", "400", "format", "malformed", "parameter"], LLMErrorCode.ERROR_INVALID_REQUEST),
        (["server", "503", "502", "504", "500", "unavailable"], LLMErrorCode.ERROR_SERVER),
        (["timeout", "timed out"], LLMErrorCode.ERROR_TIMEOUT),
        (["connect", "network", "unreachable", "dns"], LLMErrorCode.ERROR_CONNECTION),
        (["filter", "content", "policy", "blocked", "safety", "inappropriate"], LLMErrorCode.ERROR_CONTENT_FILTER),
        (["model", "not found", "does not exist", "not available"], LLMErrorCode.ERROR_MODEL),
        (["max rounds"], LLMErrorCode.ERROR_MODEL),
    ):
        if any(w in msg for w in signals):
            return code
    return LLMErrorCode.ERROR_GENERIC


def get_delay(base_delay):
    return base_delay * random.uniform(10, 150)


def retry(method):
    """Decorator: retry on transient errors with backoff.

    Works on any class — uses getattr defaults so no __init__ changes needed.
    Override by setting self.max_retries and/or self.base_delay on the instance.
    Re-raises the exception after exhausting retries or for non-retryable errors.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        max_retries = getattr(self, "max_retries", int(os.environ.get("LLM_MAX_RETRIES", 5)))
        base_delay = getattr(self, "base_delay", float(os.environ.get("LLM_BASE_DELAY", 2.0)))
        for attempt in range(max_retries + 1):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                if attempt == max_retries or not is_retryable(e):
                    raise
                delay = get_delay(base_delay)
                logging.warning(f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)

    return wrapper


def soft_retry(error_result):
    """Decorator: retry on transient errors with backoff, returning error_result on failure.

    Unlike retry(), which re-raises exceptions, soft_retry() returns
    error_result(exception) when retries are exhausted or the error is not retryable.
    This preserves backward compatibility with methods that returned ("**ERROR**: ...", 0)
    tuples instead of raising.

    Args:
        error_result: callable that takes the exception and returns the error value.
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            max_retries = getattr(self, "max_retries", int(os.environ.get("LLM_MAX_RETRIES", 5)))
            base_delay = getattr(self, "base_delay", float(os.environ.get("LLM_BASE_DELAY", 2.0)))
            for attempt in range(max_retries + 1):
                try:
                    return method(self, *args, **kwargs)
                except Exception as e:
                    if attempt == max_retries or not is_retryable(e):
                        return error_result(e)
                    delay = get_delay(base_delay)
                    logging.warning(f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)

        return wrapper

    return decorator
