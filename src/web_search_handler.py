from ui.settings import Settings
from langchain_community.document_loaders import WebBaseLoader
import os
import logging
import sys
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from langchain_community.utilities.brave_search import BraveSearchWrapper
from langchain_community.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper
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

    def __init__(self):
        """Initialize web search handler."""
        self.settings = Settings()
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

        # Only initialize the default provider to avoid wasting API credits
        logging.info(
            f"Reinitializing search providers with default provider: {default_provider}")
        self._initialize_provider(default_provider)

        # Log available providers
        if self.search_providers:
            logging.info(
                f"Successfully initialized search provider: {', '.join(self.search_providers.keys())}")
        else:
            logging.warning(
                f"Failed to initialize default provider '{default_provider}'. Please check API keys.")

    def _initialize_provider(self, provider: str):
        """Initialize a specific search provider."""
        try:
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
                        # Set reasonable defaults with more conservative settings to avoid rate limiting
                        ddg_wrapper = DuckDuckGoSearchAPIWrapper(
                            max_results=5,  # Lower default max results to avoid rate limiting
                            region="wt-wt",  # Default region (worldwide)
                            safesearch="moderate",  # Default safe search
                            time=None,  # Default time (all time)
                            backend="api"  # Use the API backend
                        )
                        # Add it to available providers without testing
                        logging.info(
                            "Adding DuckDuckGo search wrapper to available providers")
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

                        # Validate the API key before initializing
                        if self._is_valid_tavily_api_key(api_key):
                            if TavilyWrapper == TavilySearchResults:
                                # New implementation
                                self.search_providers['tavily_search'] = TavilyWrapper(
                                    max_results=5)
                            else:
                                # Old implementation
                                self.search_providers['tavily_search'] = TavilyWrapper(
                                    api_key=api_key)
                            logging.info(
                                "Tavily search provider initialized successfully")
                        else:
                            logging.error(
                                "Failed to initialize Tavily search provider: Invalid API key")
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

            # Check if LLM handler is available
            from llm_handler import LLMHandler
            llm_handler = LLMHandler()

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

            # Create a prompt to optimize the search query
            prompt = f"""You are an AI assistant designed to generate effective search queries. When a user needs information, create queries that will retrieve the most relevant results across different search engines.

To generate optimal search queries:

1. Prioritize natural language over search operators (avoid OR, AND, quotes unless necessary)
2. Format queries conversationally as complete questions when possible
3. Include specific key terms, especially for technical or specialized topics
4. Incorporate relevant time frames if the information needs to be current
5. Keep queries concise (4-7 words is often ideal) but complete
6. Avoid ambiguous terms that could have multiple meanings
7. Use synonyms for important concepts to broaden coverage

The search query should be clear, focused, and unlikely to retrieve irrelevant results. Provide ONLY the search query text with no additional explanation or commentary.

USER QUERY: "{user_query}"
"""

            # Add selected text context if available
            if selected_text and selected_text.strip():
                prompt += f"""
SELECTED TEXT: 
{selected_text.strip()}

Based on both the USER QUERY and the SELECTED TEXT above, generate an optimized search query.
"""

            prompt += "OPTIMIZED SEARCH QUERY:"

            # Get the optimized query from the LLM
            optimized_query = llm_handler.get_response(
                prompt, session_id="web_search_optimization")

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
        Perform a web search using the specified provider.

        Args:
            query: The search query
            provider: The search provider to use (defaults to the default provider in settings)
            max_results: Maximum number of results to return (defaults to settings value)

        Returns:
            List of search results
        """
        # Reset cancellation flag at the start of a new search
        self._cancellation_requested = False

        logging.info(f"WebSearchHandler.search called with query: '{query}'")

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

        # Check if provider is available
        if provider not in self.search_providers:
            available_providers = list(self.search_providers.keys())
            logging.info(f"Available search providers: {available_providers}")

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
            logging.info(f"Performing search with provider: {provider}")

            # Different providers have different methods/return formats
            if provider == 'google_serper':
                logging.info("Using Google Serper search")
                # Check if cancellation was requested
                if self._cancellation_requested:
                    logging.info("Google Serper search cancelled")
                    return []
                results = search_provider.results(query)
                # Extract organic results
                search_results = results.get('organic', [])[:max_results]
                logging.info(
                    f"Google Serper search returned {len(search_results)} results")
                return [
                    {
                        'title': result.get('title', ''),
                        'snippet': result.get('snippet', ''),
                        'link': result.get('link', '')
                    }
                    for result in search_results
                ]

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
        Scrape content from the provided URLs.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of Document objects containing the scraped content
        """
        documents = []

        # Limit the number of URLs to scrape to avoid hanging
        max_urls = self.settings.get(
            'web_search', 'max_scrape_urls', default=5)
        urls = urls[:max_urls]

        for url in urls:
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
                            logging.info(
                                f"Scraping content from {url} with timeout")
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            }
                            # Increased from 10 to 20 seconds
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
                            doc = Document(page_content=content,
                                           metadata={"source": url})
                            website_doc = doc
                            logging.info(
                                f"Successfully scraped content from {url} using requests/BeautifulSoup")

                        except (ImportError, Exception) as e:
                            # Fall back to WebBaseLoader if requests/BS4 approach fails
                            logging.warning(
                                f"Falling back to WebBaseLoader for {url}: {str(e)}")
                            loader = WebBaseLoader(url)
                            docs = loader.load()
                            if docs:
                                website_doc = docs[0]
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

    def search_and_scrape(self, query: str, provider: Optional[str] = None, max_results: Optional[int] = None, optimize_query: bool = True, selected_text: str = None) -> Dict[str, Any]:
        """
        Perform a web search and scrape content from the results.

        Args:
            query: The search query
            provider: The search provider to use
            max_results: Maximum number of results to return
            optimize_query: Whether to optimize the query using LLM before searching
            selected_text: Optional selected text to incorporate into the query optimization

        Returns:
            Dictionary containing search results and scraped content
        """
        # Reset cancellation flag at the start
        self._cancellation_requested = False

        # Optimize the query if requested
        original_query = query
        if optimize_query:
            try:

                # Optimize the query, including selected text if available
                query = self.generate_optimized_search_query(
                    query, selected_text)

                # Log the optimized query
                logging.info(f"Using optimized search query: {query}")
            except Exception as e:
                logging.error(f"Error optimizing search query: {str(e)}")
                # Use the original query if optimization fails
                query = original_query
                logging.info(f"Falling back to original query: {query}")

        # Check if scraping is enabled
        scrape_content = self.settings.get(
            'web_search', 'scrape_content', default=True)

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
