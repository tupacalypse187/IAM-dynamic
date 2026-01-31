"""
Retry mechanism with exponential backoff for transient failures
"""
import time
import logging
from typing import Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        """
        Initialize retry configuration

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff calculation
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retrying function calls with exponential backoff

    Args:
        config: Retry configuration (uses defaults if None)
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called before each retry

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts - 1:
                        # Last attempt, give up
                        logger.error(
                            f"Function {func.__name__} failed after {config.max_attempts} attempts"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for "
                        f"{func.__name__}: {str(e)}. Retrying in {delay:.2f}s..."
                    )

                    # Call on_retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)

                    time.sleep(delay)

            # Should never reach here
            raise last_exception

        return wrapper

    return decorator


class RetryableError(Exception):
    """Base exception for errors that should trigger a retry"""
    pass


class MaxRetriesExceededError(Exception):
    """Raised when max retry attempts are exceeded"""
    pass


def should_retry_exception(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry

    Args:
        exception: The exception to evaluate

    Returns:
        True if the exception should trigger a retry
    """
    # Retry on transient network errors
    error_msg = str(exception).lower()

    transient_keywords = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "transient",
        "rate limit",
        "throttle",
        "service unavailable",
        "503",
        "502",
        "500"
    ]

    return any(keyword in error_msg for keyword in transient_keywords)
