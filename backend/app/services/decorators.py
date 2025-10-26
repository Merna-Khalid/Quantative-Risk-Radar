import time
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

def log_execution(func: Callable) -> Callable:
    """Log execution time of function."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start = time.time()
        logger.info(f"[START] {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"[SUCCESS] {func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"[ERROR] {func.__name__} failed after {duration:.2f}s: {e}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start = time.time()
        logger.info(f"[START] {func.__name__}")
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"[SUCCESS] {func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"[ERROR] {func.__name__} failed after {duration:.2f}s: {e}")
            raise
    
    return async_wrapper if hasattr(func, '__await__') else sync_wrapper

def safe_execute(func: Callable) -> Callable:
    """Safely execute function with error handling."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[SAFE_EXECUTE] {func.__name__} failed: {e}")
            return {"error": str(e), "function": func.__name__}
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"[SAFE_EXECUTE] {func.__name__} failed: {e}")
            return {"error": str(e), "function": func.__name__}
    
    return async_wrapper if hasattr(func, '__await__') else sync_wrapper