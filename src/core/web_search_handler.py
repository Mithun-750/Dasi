from ui.settings import Settings
from langchain_community.document_loaders import WebBaseLoader
import os
import logging
import sys
import re
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from langchain_community.utilities.brave_search import BraveSearchWrapper
from langchain_community.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper
from .prompts_hub import (
    WEB_SEARCH_QUERY_OPTIMIZATION_TEMPLATE,
    WEB_SEARCH_RESULTS_INSTRUCTION,
    SCRAPED_CONTENT_INSTRUCTION
)
# Exa is now in a separate package
try:
    from langchain_exa import ExaSearchRetriever
    from exa_py import Exa
    has_exa = True
except ImportError:
    has_exa = False

# Check if duckduckgo-search is available
try:
    from duckduckgo_search import DDGS
    has_ddgs = True
    logging.info("Using duckduckgo_search DDGS implementation")
except ImportError:
    has_ddgs = False
    logging.warning(
        "duckduckgo-search package not available or not properly installed")

# Ensure console logging is enabled
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Check if the handler is already added to avoid duplicates
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    logger.addHandler(console_handler)

# Try both old and new Tavily implementations
has_tavily = False
try:
    # Try the newer implementation first
    from langchain_community.tools import TavilySearchResults
    has_tavily = True
    TavilyWrapper = TavilySearchResults
    logging.info("Using newer TavilySearchResults implementation")
except ImportError:
    try:
        # Fall back to the older implementation
        from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
        has_tavily = True
        TavilyWrapper = TavilySearchAPIWrapper
        logging.info("Using older TavilySearchAPIWrapper implementation")
    except ImportError:
        logging.warning("Tavily search package not available")


class WebSearchHandler:
    """Handler for web search functionality."""

    def __init__(self, llm_handler):
        """Initialize web search handler."""
        self.settings = Settings()
        self.llm_handler = llm_handler  # Store the passed LLM handler
        self.search_providers = {}
        self.initialize_search_providers()
        self._cancellation_requested = False

        # Connect to settings changes
        self.settings.web_search_changed.connect(
            self.initialize_search_providers)

    def _is_valid_tavily_api_key(self, api_key: str) -> bool:
        """Check if the provided Tavily API key is valid by making a test request."""
        if not has_tavily:
            logging.error("Tavily search package not available")
            return False

        try:
            # Set the environment variable temporarily for this test
            original_api_key = os.environ.get("TAVILY_API_KEY")
            os.environ["TAVILY_API_KEY"] = api_key

            logging.info(
                f"Testing Tavily API key: {api_key[:5]}...{api_key[-5:]}")

            # Create a temporary instance to test the API key
            if TavilyWrapper == TavilySearchResults:
                # New implementation
                logging.info(
                    "Using TavilySearchResults for API key validation")
                test_wrapper = TavilyWrapper(max_results=1)
                # Make a minimal test query
                test_result = test_wrapper.invoke("test")
                logging.info(
                    f"Tavily API key validation successful with TavilySearchResults: {len(test_result)} results")
            else:
                # Old implementation
                logging.info(
                    "Using TavilySearchAPIWrapper for API key validation")
                test_wrapper = TavilyWrapper(api_key=api_key)
                # Make a minimal test query
                test_result = test_wrapper.results("test", max_results=1)
                logging.info(
                    f"Tavily API key validation successful with TavilySearchAPIWrapper: {len(test_result.get('results', []))} results")

            # Restore the original environment variable
            if original_api_key:
                os.environ["TAVILY_API_KEY"] = original_api_key
            else:
                os.environ.pop("TAVILY_API_KEY", None)

            return True
        except Exception as e:
            logging.error(f"Invalid Tavily API key: {str(e)}")

            # Restore the original environment variable
            if original_api_key:
                os.environ["TAVILY_API_KEY"] = original_api_key
            else:
                os.environ.pop("TAVILY_API_KEY", None)

            return False

    def initialize_search_providers(self):
        """Initialize search providers based on settings."""
        # Clear existing providers
        self.search_providers = {}

        # Get default provider
        default_provider = self.settings.get(
            'web_search', 'default_provider', default='google_serper')

        logging.info(
            f"Initializing search providers with default provider: {default_provider}")

        # Check if API key exists for the default provider
        if default_provider == 'google_serper':
            api_key = self.settings.get_api_key('google_serper')
            logging.info(f"Google Serper API key exists: {bool(api_key)}")
            if not api_key:
                logging.warning(
                    "Google Serper API key is missing or empty. Please add it in settings.")
        elif default_provider == 'brave_search':
            api_key = self.settings.get_api_key('brave_search')
            logging.info(f"Brave Search API key exists: {bool(api_key)}")
            if not api_key:
                logging.warning(
                    "Brave Search API key is missing or empty. Please add it in settings.")
        elif default_provider == 'tavily_search':
            api_key = self.settings.get_api_key('tavily_search')
            logging.info(f"Tavily Search API key exists: {bool(api_key)}")
            if not api_key:
                logging.warning(
                    "Tavily Search API key is missing or empty. Please add it in settings.")
        elif default_provider == 'exa_search':
            api_key = self.settings.get_api_key('exa_search')
            logging.info(f"Exa Search API key exists: {bool(api_key)}")
            if not api_key:
                logging.warning(
                    "Exa Search API key is missing or empty. Please add it in settings.")
        elif default_provider == 'ddg_search':
            logging.info(
                "DuckDuckGo search doesn't require an API key. Checking DDGS availability.")
            logging.info(f"DDGS available: {has_ddgs}")

        # Only initialize the default provider to avoid wasting API credits
        self._initialize_provider(default_provider)

        # Log available providers
        if self.search_providers:
            logging.info(
                f"Successfully initialized search provider: {', '.join(self.search_providers.keys())}")
        else:
            logging.warning(
                f"Failed to initialize default provider '{default_provider}'. Please check API keys.")

            # Try to fallback to DuckDuckGo if available and no other provider is working
            if default_provider != 'ddg_search' and has_ddgs:
                logging.info(
                    "Attempting to initialize DuckDuckGo as fallback provider")
                self._initialize_provider('ddg_search')
                if 'ddg_search' in self.search_providers:
                    logging.info(
                        "Successfully initialized DuckDuckGo as fallback provider")
                else:
                    logging.error(
                        "Failed to initialize DuckDuckGo fallback provider")

        logging.info(
            f"Available search providers after initialization: {list(self.search_providers.keys())}")

    def _initialize_provider(self, provider: str):
        """Initialize a specific search provider."""
        try:
            # Get max_results from settings once for all providers
            max_results = self.settings.get(
                'web_search', 'max_results', default=3)
            logging.info(
                f"Initializing provider {provider} with max_results={max_results}")

            if provider == 'google_serper':
                api_key = self.settings.get_api_key('google_serper')
                if api_key:
                    self.search_providers['google_serper'] = GoogleSerperAPIWrapper(
                        serper_api_key=api_key
                    )

            elif provider == 'brave_search':
                api_key = self.settings.get_api_key('brave_search')
                if api_key:
                    self.search_providers['brave_search'] = BraveSearchWrapper(
                        api_key=api_key
                    )

            elif provider == 'ddg_search':
                # DuckDuckGo doesn't require an API key
                # Check if the DDGS class is available (new implementation)
                if has_ddgs:
                    try:
                        # Create a DDGS instance
                        logging.info(
                            "Initializing DuckDuckGo search with DDGS implementation")
                        ddg_client = DDGS()
                        self.search_providers['ddg_search'] = ddg_client
                        logging.info(
                            "Successfully initialized DuckDuckGo search with DDGS")
                    except Exception as e:
                        logging.error(
                            f"Failed to initialize DuckDuckGo search with DDGS: {str(e)}")
                else:
                    # Fall back to the LangChain wrapper if DDGS is not available
                    try:
                        # Get max_results from settings
                        max_results = self.settings.get(
                            'web_search', 'max_results', default=3)

                        # Set reasonable defaults with more conservative settings to avoid rate limiting
                        ddg_wrapper = DuckDuckGoSearchAPIWrapper(
                            max_results=max_results,  # Use configured max_results value
                            region="wt-wt",  # Default region (worldwide)
                            safesearch="moderate",  # Default safe search
                            time=None,  # Default time (all time)
                            backend="api"  # Use the API backend
                        )
                        # Add it to available providers without testing
                        logging.info(
                            f"Adding DuckDuckGo search wrapper to available providers with max_results={max_results}")
                        self.search_providers['ddg_search'] = ddg_wrapper
                    except Exception as e:
                        logging.error(
                            f"Failed to initialize DuckDuckGo search wrapper: {str(e)}")

            elif provider == 'exa_search':
                api_key = self.settings.get_api_key('exa_search')
                if api_key and has_exa:
                    # Use Exa client directly
                    exa_client = Exa(api_key=api_key)
                    self.search_providers['exa_search'] = exa_client

            elif provider == 'tavily_search':
                if not has_tavily:
                    logging.error("Tavily search package not available")
                    return

                api_key = self.settings.get_api_key('tavily_search')
                if api_key:
                    try:
                        # Set the environment variable for Tavily
                        os.environ["TAVILY_API_KEY"] = api_key

                        # Initialize directly without validation
                        if TavilyWrapper == TavilySearchResults:
                            # New implementation - use max_results from settings
                            self.search_providers['tavily_search'] = TavilyWrapper(
                                max_results=max_results)
                            logging.info(
                                f"Tavily search provider initialized with max_results={max_results}")
                        else:
                            # Old implementation
                            self.search_providers['tavily_search'] = TavilyWrapper(
                                api_key=api_key)
                        logging.info(
                            "Tavily search provider initialized successfully")

                    except Exception as e:
                        logging.error(
                            f"Error initializing Tavily search provider: {str(e)}")
                else:
                    logging.warning(
                        "Tavily search provider requires an API key. Please add it in settings.")
                    # If Tavily is set as default but has no API key, log a specific warning
                    default_provider = self.settings.get(
                        'web_search', 'default_provider', default='google_serper')
                    if default_provider == 'tavily_search':
                        logging.warning(
                            "Tavily is set as default search provider but no API key is provided. Will fall back to another provider.")
        except Exception as e:
            logging.error(
                f"Error initializing search provider {provider}: {str(e)}")

    def cancel_search(self):
        """Cancel any ongoing search operation."""
        logging.info("Cancellation of web search requested")
        self._cancellation_requested = True

    def reset_cancellation(self):
        """Reset the cancellation flag."""
        self._cancellation_requested = False

    def generate_optimized_search_query(self, user_query: str, selected_text: str = None) -> str:
        """
        Generate an optimized search query using the LLM.

        Args:
            user_query: The original user query
            selected_text: Optional selected text to incorporate into the query

        Returns:
            An optimized search query
        """
        try:
            # Add a small delay to ensure users see the query optimization step
            # This improves UX by showing the actual optimization happening
            import time
            time.sleep(0.8)  # 800ms delay

            # Use the stored LLM handler instance
            if not self.llm_handler:
                logging.error("LLM Handler not available in WebSearchHandler")
                return user_query

            # Check if the user_query already contains the template text (recursive case)
            template_start = "You are an AI assistant designed to generate effective search queries."
            if template_start in user_query:
                # Extract the actual query from the recursive template
                query_marker = "USER QUERY: \""
                if query_marker in user_query:
                    # Find the last occurrence in case of recursion
                    start_index = user_query.rindex(
                        query_marker) + len(query_marker)
                    # Find the closing quote, or just take the rest if no quote
                    end_index = user_query.rfind("\"", start_index)
                    if end_index == -1:
                        actual_query = user_query[start_index:]
                    else:
                        actual_query = user_query[start_index:end_index]

                    # Clean up and use this as the query
                    actual_query = actual_query.strip()
                    if actual_query:
                        user_query = actual_query
                        logging.info(
                            f"Extracted inner query from recursive template: {user_query}")

            # Create a prompt to optimize the search query using the template from prompts_hub
            prompt = WEB_SEARCH_QUERY_OPTIMIZATION_TEMPLATE.format(
                user_query=user_query)

            # Add selected text context if available
            if selected_text and selected_text.strip():
                prompt += f"""
SELECTED TEXT: 
{selected_text.strip()}

Based on both the USER QUERY and the SELECTED TEXT above, generate an optimized search query.
"""

            prompt += "OPTIMIZED SEARCH QUERY:"

            # Get the model currently used by the main LLM Handler instance
            model = None
            if self.llm_handler.llm:
                if hasattr(self.llm_handler.llm, 'model'):
                    model = self.llm_handler.llm.model
                elif hasattr(self.llm_handler.llm, 'model_name'):
                    model = self.llm_handler.llm.model_name
            logging.info(
                f"Using model {model} from main LLM handler for search query optimization")

            # Get the optimized query from the stored LLM handler
            optimized_query = self.llm_handler.get_response(
                prompt, session_id="web_search_optimization", model=model)

            # Clean up the response (remove quotes, explanation text, etc.)
            optimized_query = optimized_query.strip()

            # Remove leading/trailing quotes if present
            if optimized_query.startswith('"') and optimized_query.endswith('"'):
                optimized_query = optimized_query[1:-1].strip()
            elif optimized_query.startswith("'") and optimized_query.endswith("'"):
                optimized_query = optimized_query[1:-1].strip()

            # Remove any explanatory text that might have been included
            if ":" in optimized_query and len(optimized_query.split(":", 1)) > 1:
                # Check if there's introduction text like "Search query:" at the beginning
                parts = optimized_query.split(":", 1)
                if len(parts[0].split()) <= 3:  # If first part has 3 or fewer words
                    optimized_query = parts[1].strip()

            # If the result is too long, truncate it to a reasonable length
            if len(optimized_query) > 150:
                optimized_query = optimized_query[:150]

            # Ensure the query is not empty
            if not optimized_query:
                logging.warning(
                    "LLM returned empty search query, using original query")
                return user_query

            logging.info(
                f"Generated optimized search query: {optimized_query}")
            return optimized_query

        except Exception as e:
            logging.error(f"Error generating optimized search query: {str(e)}")
            # Fall back to the original query
            return user_query

    def search(self, query: str, provider: Optional[str] = None, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Execute a search using the specified provider.

        Args:
            query: The search query
            provider: Optional search provider name
            max_results: Maximum number of results to return

        Returns:
            List of search results
        """
        # Reset cancellation flag at the start of a new search
        self._cancellation_requested = False

        logging.info(f"WebSearchHandler.search called with query: '{query}'")
        logging.info(
            f"Currently available search providers: {list(self.search_providers.keys())}")

        # Get default provider if none specified
        if not provider:
            provider = self.settings.get(
                'web_search', 'default_provider', default='google_serper')
            logging.info(f"Using default search provider: {provider}")
        else:
            logging.info(f"Using specified search provider: {provider}")

        # Get max results if none specified
        if not max_results:
            max_results = self.settings.get(
                'web_search', 'max_results', default=5)
            logging.info(f"Using default max_results: {max_results}")
        else:
            logging.info(f"Using specified max_results: {max_results}")

        # Check if provider is available
        if provider not in self.search_providers:
            available_providers = list(self.search_providers.keys())
            logging.warning(
                f"Provider '{provider}' not available. Available providers: {available_providers}")

            if not available_providers:
                error_msg = "No search providers are available. Please add API keys in settings."
                logging.error(error_msg)
                raise ValueError(error_msg)

            # Use first available provider as fallback
            original_provider = provider
            provider = available_providers[0]
            logging.warning(
                f"Provider '{original_provider}' not available. Using '{provider}' instead.")

            # If the requested provider was Tavily, provide more specific guidance
            if original_provider == 'tavily_search':
                logging.warning(
                    "To use Tavily search, please ensure you have added a valid Tavily API key in settings.")

        try:
            # Check if cancellation was requested
            if self._cancellation_requested:
                logging.info("Search cancelled before starting")
                return []

            # Perform search with ONLY the specified/default provider
            search_provider = self.search_providers[provider]
            logging.info(
                f"Executing search with provider: {provider}, type: {type(search_provider).__name__}")

            # Different providers have different methods/return formats
            if provider == 'google_serper':
                logging.info(
                    f"Starting Google Serper search for query: {query}")
                # Check if cancellation was requested
                if self._cancellation_requested:
                    logging.info("Google Serper search cancelled")
                    return []

                results = search_provider.results(query)

                # Extract organic results
                search_results = results.get('organic', [])[:max_results]
                logging.info(
                    f"Google Serper search returned {len(search_results)} results")

                formatted_results = [
                    {
                        'title': result.get('title', ''),
                        'snippet': result.get('snippet', ''),
                        'link': result.get('link', '')
                    }
                    for result in search_results
                ]
                logging.info(
                    f"Returning {len(formatted_results)} formatted results from Google Serper")
                return formatted_results

            elif provider == 'brave_search':
                logging.info("Using Brave search")
                # Check if cancellation was requested
                if self._cancellation_requested:
                    logging.info("Brave search cancelled")
                    return []
                # BraveSearchWrapper.run returns a JSON string, so we need to parse it
                import json
                results_json = search_provider.run(query)
                results = json.loads(results_json)

                # Extract the web results
                web_results = results.get('web', {}).get('results', [])
                logging.info(
                    f"Brave search returned {len(web_results)} results")
                return [
                    {
                        'title': result.get('title', ''),
                        'snippet': result.get('description', ''),
                        'link': result.get('url', '')
                    }
                    for result in web_results[:max_results]
                ]

            elif provider == 'ddg_search':
                logging.info("Using DuckDuckGo search")
                try:
                    # Check if cancellation was requested
                    if self._cancellation_requested:
                        logging.info("DuckDuckGo search cancelled")
                        return []

                    # Get max results if not specified
                    if not max_results:
                        max_results = self.settings.get(
                            'web_search', 'max_results', default=5)

                    # Limit max results to avoid rate limiting
                    max_results = min(max_results, 10)

                    logging.info(
                        f"Calling DuckDuckGo search with query: {query}, max_results: {max_results}")

                    # Check if we're using the DDGS implementation
                    if has_ddgs and isinstance(search_provider, DDGS):
                        logging.info(
                            "Using DDGS implementation for DuckDuckGo search")
                        try:
                            # Check if cancellation was requested
                            if self._cancellation_requested:
                                logging.info("DDGS search cancelled")
                                return []

                            # Use the text search method from DDGS
                            search_results = list(search_provider.text(
                                query,
                                max_results=max_results,
                                region="wt-wt",  # Worldwide region
                                safesearch="moderate"  # Moderate safe search
                            ))

                            if not search_results:
                                logging.warning(
                                    "DuckDuckGo search returned no results")
                                return []

                            logging.info(
                                f"DuckDuckGo search returned {len(search_results)} results")

                            # Format results to match our standard format
                            formatted_results = []
                            for result in search_results:
                                formatted_results.append({
                                    'title': result.get('title', ''),
                                    'snippet': result.get('body', ''),
                                    'link': result.get('href', '')
                                })

                            return formatted_results
                        except Exception as e:
                            logging.error(f"Error with DDGS search: {str(e)}")
                            return []

                    # Fall back to the LangChain wrapper if not using DDGS
                    if isinstance(search_provider, DuckDuckGoSearchAPIWrapper):
                        logging.info(
                            "Using DuckDuckGoSearchAPIWrapper for search")
                        try:
                            # Check if cancellation was requested
                            if self._cancellation_requested:
                                logging.info(
                                    "DuckDuckGoSearchAPIWrapper search cancelled")
                                return []

                            search_results = search_provider.results(
                                query, max_results=max_results)

                            # Check if results is None or empty
                            if not search_results:
                                logging.warning(
                                    "DuckDuckGo search returned no results")
                                return []

                            logging.info(
                                f"DuckDuckGo search returned {len(search_results)} results")

                            # Standard format for results
                            formatted_results = []
                            for result in search_results:
                                formatted_results.append({
                                    'title': result.get('title', ''),
                                    'snippet': result.get('body', ''),
                                    'link': result.get('href', '')
                                })

                            return formatted_results
                        except Exception as api_error:
                            logging.error(
                                f"Error executing DuckDuckGo search: {str(api_error)}")
                            # Log more details to help diagnose the issue
                            import traceback
                            logging.error(traceback.format_exc())
                            return []

                    # If we get here, we don't have a valid search provider
                    logging.error(
                        f"DuckDuckGo search provider is not a recognized type: {type(search_provider)}")
                    return []

                except Exception as e:
                    logging.error(f"Error with DuckDuckGo search: {str(e)}")
                    return []

            elif provider == 'exa_search':
                logging.info("Using Exa search")
                # Use the Exa client's search_and_contents method
                try:
                    # Check if cancellation was requested
                    if self._cancellation_requested:
                        logging.info("Exa search cancelled")
                        return []

                    results = search_provider.search_and_contents(
                        query,
                        num_results=max_results,
                        text=True,
                        highlights=True
                    )

                    # Check if results has a results attribute (newer Exa API)
                    if hasattr(results, 'results'):
                        search_results = results.results
                        logging.info(
                            f"Exa search returned {len(search_results)} results")

                        # Format the results - handle Result objects properly
                        formatted_results = []
                        for result in search_results:
                            try:
                                # Handle Result objects (which have attributes instead of dictionary keys)
                                if hasattr(result, 'title') and hasattr(result, 'url'):
                                    # Direct attribute access for Result objects
                                    title = result.title if hasattr(
                                        result, 'title') else ''
                                    url = result.url if hasattr(
                                        result, 'url') else ''

                                    # Handle text content - try different possible attributes
                                    snippet = ''
                                    if hasattr(result, 'text') and result.text:
                                        snippet = result.text
                                    elif hasattr(result, 'extract') and result.extract:
                                        snippet = result.extract
                                    elif hasattr(result, 'highlights') and result.highlights:
                                        # highlights might be a list
                                        if isinstance(result.highlights, list) and len(result.highlights) > 0:
                                            snippet = result.highlights[0]
                                        else:
                                            snippet = str(result.highlights)

                                    formatted_results.append({
                                        'title': title,
                                        'snippet': snippet,
                                        'link': url
                                    })
                                else:
                                    # Fall back to dictionary-style access if it's not a Result object
                                    formatted_results.append({
                                        'title': result.get('title', ''),
                                        'snippet': result.get('text', result.get('highlights', [''])[0] if result.get('highlights') else ''),
                                        'link': result.get('url', '')
                                    })
                            except Exception as e:
                                logging.error(
                                    f"Error processing Exa search result: {str(e)}")
                                # Try a more basic approach as fallback
                                try:
                                    formatted_results.append({
                                        'title': str(getattr(result, 'title', 'No Title')),
                                        'snippet': str(getattr(result, 'text', getattr(result, 'extract', 'No Content'))),
                                        'link': str(getattr(result, 'url', 'No URL'))
                                    })
                                except:
                                    logging.error(
                                        f"Failed to process Exa result even with fallback method")

                        return formatted_results
                    else:
                        # Handle older API or different response format
                        logging.info(
                            "Exa search returned results in a different format")
                        # Try to handle as a list directly
                        try:
                            formatted_results = []
                            for result in results:
                                # Check if cancellation was requested during processing
                                if self._cancellation_requested:
                                    logging.info(
                                        "Exa search result processing cancelled")
                                    return formatted_results

                                try:
                                    # Try attribute access first (for Result objects)
                                    if hasattr(result, 'title') and hasattr(result, 'url'):
                                        title = result.title if hasattr(
                                            result, 'title') else ''
                                        url = result.url if hasattr(
                                            result, 'url') else ''

                                        # Handle text content
                                        snippet = ''
                                        if hasattr(result, 'text') and result.text:
                                            snippet = result.text
                                        elif hasattr(result, 'extract') and result.extract:
                                            snippet = result.extract
                                        elif hasattr(result, 'highlights') and result.highlights:
                                            if isinstance(result.highlights, list) and len(result.highlights) > 0:
                                                snippet = result.highlights[0]
                                            else:
                                                snippet = str(
                                                    result.highlights)

                                        formatted_results.append({
                                            'title': title,
                                            'snippet': snippet,
                                            'link': url
                                        })
                                    else:
                                        # Fall back to dictionary access
                                        formatted_results.append({
                                            'title': result.get('title', ''),
                                            'snippet': result.get('text', result.get('highlights', [''])[0] if result.get('highlights') else ''),
                                            'link': result.get('url', '')
                                        })
                                except Exception as e:
                                    logging.error(
                                        f"Error processing individual Exa result: {str(e)}")

                            return formatted_results
                        except Exception as e:
                            logging.error(
                                f"Failed to process Exa search results: {str(e)}")
                            return []
                except Exception as e:
                    logging.error(f"Error performing Exa search: {str(e)}")
                    return []

            elif provider == 'tavily_search':
                logging.info("Using Tavily search")
                try:
                    # Check if cancellation was requested
                    if self._cancellation_requested:
                        logging.info("Tavily search cancelled")
                        return []

                    if not hasattr(search_provider, 'results') and not hasattr(search_provider, 'invoke'):
                        logging.error(
                            "Tavily search provider does not have a valid method. This may indicate an initialization issue.")
                        return []

                    # Set the environment variable for Tavily
                    os.environ["TAVILY_API_KEY"] = self.settings.get_api_key(
                        'tavily_search')

                    if hasattr(search_provider, 'invoke'):
                        # New implementation
                        logging.info("Using Tavily invoke method")
                        results = search_provider.invoke(query)

                        # Check if results is None or empty
                        if not results:
                            logging.warning(
                                "Tavily search returned no results")
                            return []

                        logging.info(
                            f"Tavily search returned {len(results)} results")
                        # Format results from the new implementation
                        return [
                            {
                                'title': result.get('title', ''),
                                'snippet': result.get('content', ''),
                                'link': result.get('url', '')
                            }
                            for result in results
                        ]
                    else:
                        # Old implementation
                        logging.info("Using Tavily results method")
                        results = search_provider.results(
                            query, max_results=max_results)

                        # Check if results is None or empty
                        if not results:
                            logging.warning(
                                "Tavily search returned no results")
                            return []

                        # Check if 'results' key exists in the response
                        if 'results' not in results:
                            logging.error(
                                f"Unexpected Tavily search response format: {results}")
                            return []

                        logging.info(
                            f"Tavily search returned {len(results.get('results', []))} results")
                        return [
                            {
                                'title': result.get('title', ''),
                                'snippet': result.get('content', ''),
                                'link': result.get('url', '')
                            }
                            for result in results.get('results', [])
                        ]
                except Exception as e:
                    logging.error(f"Error performing Tavily search: {str(e)}")
                    return []

            # Default case if provider is not recognized
            logging.warning(f"Unrecognized provider: {provider}")
            return []

        except Exception as e:
            logging.error(
                f"Error performing search with provider {provider}: {str(e)}")
            return []  # Return empty list instead of raising exception

    def scrape_content(self, urls: List[str]) -> List[Document]:
        """
        Scrape content from the provided URLs, stripping URL fragments.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of Document objects containing the scraped content
        """
        import urllib.parse

        documents = []

        # Limit the number of URLs to scrape to avoid hanging
        max_urls = self.settings.get(
            'web_search', 'max_scrape_urls', default=5)
        urls = urls[:max_urls]

        for raw_url in urls:
            # --- NEW: Strip fragment from URL --- START ---
            try:
                parsed_url = urllib.parse.urlparse(raw_url)
                # Reconstruct URL without the fragment
                url = urllib.parse.urlunparse(
                    (parsed_url.scheme, parsed_url.netloc, parsed_url.path,
                     parsed_url.params, parsed_url.query, '')  # Empty fragment
                )
                if raw_url != url:
                    logging.info(
                        f"Stripped fragment from URL: '{raw_url}' -> '{url}'")
            except Exception as parse_err:
                logging.error(
                    f"Failed to parse or strip fragment from URL '{raw_url}': {parse_err}. Using raw URL.")
                url = raw_url  # Fallback to raw URL if parsing fails
            # --- NEW: Strip fragment from URL --- END ----

            # Check if cancellation was requested between URL scraping
            if self._cancellation_requested:
                logging.info(
                    f"Scraping cancelled. Processed {len(documents)} documents before cancellation.")
                return documents

            # Add a per-website timeout mechanism
            try:
                # Set a per-website timeout - if this is exceeded, skip to the next website
                import threading
                import time

                website_scrape_completed = False
                website_doc = None
                website_error = None

                def scrape_single_website():
                    nonlocal website_scrape_completed, website_doc, website_error
                    try:
                        # Use a custom loader with shorter timeouts
                        try:
                            import requests
                            from bs4 import BeautifulSoup

                            # Use a timeout to avoid hanging
                            # Use the processed URL (fragment stripped)
                            logging.info(
                                f"Scraping content from {url} with timeout")
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            }
                            # Increased from 10 to 20 seconds
                            # Use the processed URL (fragment stripped)
                            response = requests.get(
                                url, headers=headers, timeout=20)

                            # Check for cancellation after the request
                            if self._cancellation_requested:
                                logging.info(
                                    "Scraping cancelled after request.")
                                website_scrape_completed = True
                                return

                            # Parse the content
                            soup = BeautifulSoup(
                                response.content, 'html.parser')

                            # Extract main content (naive approach - just get the text)
                            content = soup.get_text(separator='\n', strip=True)

                            # Limit content length to avoid processing excessively large pages
                            max_content_length = 50000  # ~50KB of text is plenty for most use cases
                            if len(content) > max_content_length:
                                content = content[:max_content_length] + \
                                    "\n\n[Content truncated due to length...]"
                                logging.info(
                                    f"Content from {url} truncated to {max_content_length} characters")

                            # Create a document
                            from langchain_core.documents import Document
                            # Use the processed URL (fragment stripped) in metadata
                            doc = Document(page_content=content,
                                           metadata={"source": url})
                            website_doc = doc
                            logging.info(
                                f"Successfully scraped content from {url} using requests/BeautifulSoup")

                        except (ImportError, Exception) as e:
                            # Fall back to WebBaseLoader if requests/BS4 approach fails
                            logging.warning(
                                f"Falling back to WebBaseLoader for {url}: {str(e)}")
                            # Use the processed URL (fragment stripped)
                            loader = WebBaseLoader(url)
                            docs = loader.load()
                            if docs:
                                website_doc = docs[0]
                                # Ensure source metadata uses the cleaned URL
                                if 'source' not in website_doc.metadata:
                                    website_doc.metadata['source'] = url
                                elif website_doc.metadata['source'] != url:
                                    logging.info(
                                        f"Updating WebBaseLoader metadata source to cleaned URL: {url}")
                                    website_doc.metadata['source'] = url

                            logging.info(
                                f"Successfully scraped content from {url} using WebBaseLoader")

                        website_scrape_completed = True

                    except Exception as e:
                        website_error = e
                        website_scrape_completed = True

                # Start scraping in a separate thread
                scrape_thread = threading.Thread(target=scrape_single_website)
                scrape_thread.daemon = True
                scrape_thread.start()

                # Wait for the scraping to complete with a per-website timeout
                # seconds per website (slightly longer than the request timeout)
                website_timeout = 25
                start_time = time.time()
                while not website_scrape_completed and not self._cancellation_requested:
                    scrape_thread.join(0.5)  # Check every 0.5 seconds
                    if time.time() - start_time > website_timeout:
                        logging.warning(
                            f"Scraping {url} timed out after {website_timeout} seconds, skipping to next URL")
                        break

                # If website scrape completed successfully and we have a document, add it
                if website_scrape_completed and website_doc:
                    documents.append(website_doc)

                # If there was an error, log it but continue with other URLs
                if website_error:
                    logging.error(
                        f"Error scraping content from {url}: {str(website_error)}")

                # Check cancellation again
                if self._cancellation_requested:
                    logging.info(
                        "Scraping cancelled during website processing.")
                    return documents

            except Exception as e:
                logging.error(
                    f"Error in per-website timeout mechanism for {url}: {str(e)}")
                # Continue with next URL rather than failing the entire process

        return documents

    def search_and_scrape(self, query: str, provider: Optional[str] = None, max_results: Optional[int] = None, optimize_query: bool = True, selected_text: str = None, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform a web search and scrape content from the results.

        Args:
            query: The search query
            provider: The search provider to use
            max_results: Maximum number of results to return
            optimize_query: Whether to optimize the query using LLM before searching
            selected_text: Optional selected text to incorporate into the query optimization
            model: Optional model to use for query optimization (passed from UI) - This parameter might be redundant now but kept for safety

        Returns:
            Dictionary containing search results and scraped content
        """
        # Reset cancellation flag at the start
        self._cancellation_requested = False

        # Optimize the query if requested
        original_query = query
        if optimize_query:
            try:
                # Optimize the query using the generate_optimized_search_query method
                # which now uses the correct LLM handler instance
                query = self.generate_optimized_search_query(
                    query, selected_text)

                # Log the optimized query
                logging.info(f"Using optimized search query: {query}")
            except Exception as e:
                logging.error(f"Error optimizing search query: {str(e)}")
                # Use the original query if optimization fails
                query = original_query
                logging.info(f"Falling back to original query: {query}")

        # Check if scraping is enabled - Simplified, always True now?
        # Re-evaluate if we need the scrape_content setting at all
        scrape_content = True  # Assuming scraping is always on now

        # Perform search
        search_results = self.search(query, provider, max_results)

        # Check if cancellation was requested after search
        if self._cancellation_requested:
            logging.info(
                "Web search and scrape operation cancelled after search phase")
            return {
                'search_results': search_results,
                'scraped_content': [],
                'original_query': original_query,
                'optimized_query': query if optimize_query else original_query
            }

        # Scrape content if enabled
        scraped_content = []
        if scrape_content and search_results:
            urls = [result['link'] for result in search_results]
            scraped_content = self.scrape_content(urls)

        return {
            'search_results': search_results,
            'scraped_content': scraped_content,
            'original_query': original_query,
            'optimized_query': query if optimize_query else original_query
        }

    def process_query_context(self, query: str, context: dict = None) -> dict:
        """
        Process the query and context to determine if web search or link scraping is needed.

        Args:
            query: The raw query from the user
            context: Optional context dictionary containing selected text, etc.

        Returns:
            Dictionary containing:
            - mode: 'web_search', 'link_scrape', or None
            - query: The processed query (for web search)
            - url: The URL to scrape (for link scrape)
            - original_query: The original unmodified query
        """
        result = {
            'mode': None,
            'query': query,
            'url': None,
            'original_query': query
        }

        # Direct URL detection
        url_pattern = r'(https?://[^\s]+)'
        url_match = re.search(url_pattern, query)
        if url_match:
            potential_url = url_match.group(1)
            if len(potential_url) > 15 and ('.' in potential_url):
                result['mode'] = 'link_scrape'
                result['url'] = potential_url
                logging.info(f"Detected direct URL in query: {potential_url}")
                return result

        # Check for #URL format
        hash_url_pattern = r'#(https?://[^\s]+)'
        hash_url_match = re.search(hash_url_pattern, query)
        if hash_url_match:
            hash_url = hash_url_match.group(1)
            result['mode'] = 'link_scrape'
            result['url'] = hash_url
            result['query'] = query.replace(f"#{hash_url}", "", 1).strip()
            logging.info(f"Detected #URL pattern: {hash_url}")
            return result

        # Check for web search commands
        if query.strip().startswith('#web '):
            result['mode'] = 'web_search'
            result['query'] = query.replace('#web ', '', 1).strip()
            logging.info(f"Web search requested (prefix): {result['query']}")
            return result

        if "#web" in query:
            result['mode'] = 'web_search'
            result['query'] = query.replace("#web", "").strip()
            logging.info(f"Web search requested (inline): {result['query']}")
            return result

        # Check context if provided
        if context:
            # Check for link scrape info in context
            if context.get('is_link_scrape') and context.get('link_to_scrape'):
                result['mode'] = 'link_scrape'
                result['url'] = context['link_to_scrape']
                logging.info(
                    f"Link scrape requested from context: {result['url']}")
                return result

            # Check for web search flag in context
            if context.get('web_search'):
                result['mode'] = 'web_search'
                logging.info("Web search requested from context")
                return result

        return result

    def execute_search_or_scrape(self, process_result: dict, selected_text: str = None) -> dict:
        """
        Execute the determined search or scrape operation and format results for LLM consumption.

        Args:
            process_result: Dictionary from process_query_context
            selected_text: Optional selected text for query optimization

        Returns:
            Dictionary containing:
            - status: 'success' or 'error'
            - query: The final query to send to LLM
            - system_instruction: Optional system instruction block for LLM
            - error: Error message if status is 'error'
        """
        result = {
            'status': 'success',
            'query': process_result['query'],
            'system_instruction': None,
            'error': None
        }

        logging.info(
            f"execute_search_or_scrape called with mode: {process_result['mode']}")
        logging.info(
            f"Available search providers: {list(self.search_providers.keys())}")

        # Early failure if no search providers are available
        if not self.search_providers and process_result['mode'] == 'web_search':
            result['status'] = 'error'
            result['error'] = "No search providers are configured. Please add API keys in settings."
            logging.error(
                "Web search attempted but no search providers are available")
            return result

        try:
            # Try to get the selected model from the UI
            model = None
            # Removed UI lookup for model, as the main LLM handler should have the correct model
            # try:
            #     from instance_manager import DasiInstanceManager
            #     dasi_instance = DasiInstanceManager.get_instance()
            #     if dasi_instance and dasi_instance.ui and hasattr(dasi_instance.ui, 'popup') and hasattr(dasi_instance.ui.popup, 'input_panel'):
            #         model_info = dasi_instance.ui.popup.input_panel.get_selected_model()
            #         if model_info and 'id' in model_info:
            #             model = model_info['id']
            #             logging.info(f"Using model from UI for web search: {model}")
            # except Exception as e:
            #     logging.error(f"Error getting model from UI: {str(e)}")
            #     model = None

            if process_result['mode'] == 'web_search':
                logging.info("Processing web search request")

                # Get the currently active model from the main LLM handler instance
                if self.llm_handler and self.llm_handler.llm:
                    if hasattr(self.llm_handler.llm, 'model'):
                        model = self.llm_handler.llm.model
                    elif hasattr(self.llm_handler.llm, 'model_name'):
                        model = self.llm_handler.llm.model_name
                logging.info(f"Using model {model} for search_and_scrape")

                # Perform web search and scraping with the correct model
                logging.info(
                    f"Calling search_and_scrape with query: {process_result['query']}")
                search_results = self.search_and_scrape(
                    process_result['query'],
                    optimize_query=True,
                    selected_text=selected_text,
                    model=model  # Pass the model determined from the handler
                )

                logging.info(
                    f"Search results obtained: {len(search_results.get('search_results', []))} results")

                if not search_results['search_results']:
                    result['status'] = 'error'
                    result['error'] = "No search results found."
                    logging.warning("No search results found")
                    return result

                # Format search results for LLM
                search_results_text = "=====WEB_SEARCH_RESULTS=====<results from web search>\n"

                # Add original and optimized query information
                if search_results['original_query'] != search_results['optimized_query']:
                    search_results_text += f"Original Query: {search_results['original_query']}\n"
                    search_results_text += f"Optimized Query: {search_results['optimized_query']}\n\n"

                # Add search results
                search_results_text += "Search Results:\n"
                for i, sr in enumerate(search_results['search_results']):
                    search_results_text += f"{i+1}. {sr['title']}\n"
                    search_results_text += f"   URL: {sr['link']}\n"
                    search_results_text += f"   Snippet: {sr['snippet']}\n\n"

                # Add scraped content if available
                if search_results['scraped_content']:
                    search_results_text += "Scraped Content:\n"
                    for i, doc in enumerate(search_results['scraped_content']):
                        search_results_text += f"Document {i+1} from {doc.metadata.get('source', 'unknown')}:\n"
                        content = doc.page_content
                        if len(content) > 2000:
                            content = content[:2000] + \
                                "... (content truncated)"
                        search_results_text += f"{content}\n\n"

                search_results_text += "=======================\n\n"

                # Add search results to the query
                result['query'] = f"{search_results_text}Based on the web search results above, please answer: {process_result['original_query']}"
                logging.info("Successfully formatted search results for LLM")

                # Add web search instruction from prompts_hub
                result['system_instruction'] = WEB_SEARCH_RESULTS_INSTRUCTION

            elif process_result['mode'] == 'link_scrape':
                # Scrape content from the URL
                scraped_docs = self.scrape_content([process_result['url']])

                if not scraped_docs:
                    result['status'] = 'error'
                    result['error'] = f"No content could be scraped from the URL: {process_result['url']}"
                    return result

                # Format scraped content for LLM
                scraped_content_text = "=====SCRAPED_CONTENT=====<content from the provided URL>\n"

                for i, doc in enumerate(scraped_docs):
                    scraped_content_text += f"Content from {doc.metadata.get('source', process_result['url'])}:\n"
                    content = doc.page_content
                    if len(content) > 10000:
                        content = content[:10000] + "... (content truncated)"
                    scraped_content_text += f"{content}\n\n"

                scraped_content_text += "=======================\n\n"

                # Add scraped content to the query
                result['query'] = f"{scraped_content_text}Based on the scraped content above from {process_result['url']}, please answer: {process_result['query']}"

                # Add scraped content instruction from prompts_hub
                result['system_instruction'] = SCRAPED_CONTENT_INSTRUCTION

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logging.error(f"Error in execute_search_or_scrape: {str(e)}")

        return result
