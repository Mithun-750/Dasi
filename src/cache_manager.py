import os
import json
import hashlib
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path


class CacheManager:
    """Manages caching for expensive operations to improve startup and response times."""

    def __init__(self):
        """Initialize the cache manager."""
        # Get cache directory from environment or use default
        self.cache_dir = os.environ.get(
            'DASI_CACHE_DIR', str(Path.home() / '.cache' / 'dasi'))
        self.llm_cache_dir = os.environ.get(
            'DASI_LLM_CACHE', os.path.join(self.cache_dir, 'llm_responses'))
        self.models_cache_dir = os.environ.get(
            'DASI_MODELS_CACHE', os.path.join(self.cache_dir, 'models'))

        # Create cache directories if they don't exist
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.llm_cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.models_cache_dir).mkdir(parents=True, exist_ok=True)

        # Get AppImage hash for cache invalidation if available
        self.appimage_hash = os.environ.get('DASI_APPIMAGE_HASH', '')

        logging.info(f"Cache initialized at {self.cache_dir}")
        if self.appimage_hash:
            logging.info(
                f"Using AppImage hash for cache: {self.appimage_hash}")

    def _get_cache_key(self, data: str, namespace: str = '') -> str:
        """Generate a cache key from the input data."""
        if namespace:
            data = f"{namespace}:{data}"

        # Add AppImage hash to the data if available for version-specific caching
        if self.appimage_hash:
            data = f"{data}:{self.appimage_hash}"

        return hashlib.md5(data.encode('utf-8')).hexdigest()

    def get_from_cache(self, key: str, namespace: str = '',
                       max_age: int = 86400) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache if available and not expired.

        Args:
            key: The key or data to generate a cache key from
            namespace: Optional namespace to avoid key collisions
            max_age: Maximum age of cache entry in seconds (default: 24 hours)

        Returns:
            Cached data or None if not found or expired
        """
        # Don't cache chat history sessions
        if namespace == 'chat_history':
            return None

        cache_key = self._get_cache_key(key, namespace)
        cache_file = os.path.join(self.llm_cache_dir, f"{cache_key}.json")

        if not os.path.exists(cache_file):
            return None

        try:
            # Check if cache entry is still valid
            if max_age > 0:
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age > max_age:
                    logging.debug(f"Cache entry expired: {cache_key}")
                    return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Error reading cache: {str(e)}")
            return None

    def save_to_cache(self, key: str, data: Dict[str, Any],
                      namespace: str = '') -> None:
        """
        Save data to cache.

        Args:
            key: The key or data to generate a cache key from
            data: The data to cache
            namespace: Optional namespace to avoid key collisions
        """
        # Don't cache chat history sessions
        if namespace == 'chat_history':
            return

        cache_key = self._get_cache_key(key, namespace)
        cache_file = os.path.join(self.llm_cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            logging.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            logging.warning(f"Error writing to cache: {str(e)}")

    def get_model_cache_path(self, model_id: str) -> Path:
        """
        Get path for caching model files.

        Args:
            model_id: ID of the model

        Returns:
            Path object for the model cache directory
        """
        # Sanitize model ID for use as directory name
        safe_id = model_id.replace('/', '_').replace(':', '_')
        model_dir = Path(self.models_cache_dir) / safe_id
        model_dir.mkdir(exist_ok=True)
        return model_dir

    def clear_cache(self, namespace: Optional[str] = None) -> None:
        """
        Clear all or part of the cache.

        Args:
            namespace: If provided, only clear cache for this namespace
        """
        if namespace:
            # Only clear entries for a specific namespace
            for file in Path(self.llm_cache_dir).glob("*.json"):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get('namespace') == namespace:
                        os.remove(file)
                except Exception as e:
                    logging.warning(
                        f"Error clearing cache entry {file}: {str(e)}")
        else:
            # Clear all cache entries
            for file in Path(self.llm_cache_dir).glob("*.json"):
                try:
                    os.remove(file)
                except Exception as e:
                    logging.warning(
                        f"Error removing cache file {file}: {str(e)}")
