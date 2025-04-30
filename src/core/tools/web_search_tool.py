import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal

# Assuming WebSearchHandler is in src/core/web_search_handler.py
# Adjust import path if necessary
from ..web_search_handler import WebSearchHandler


class WebSearchWorker(QThread):
    """Worker thread for performing web searches without blocking the UI."""
    search_completed = pyqtSignal(dict)

    def __init__(self, web_search_handler, process_result, selected_text):
        super().__init__()
        self.web_search_handler = web_search_handler
        self.process_result = process_result
        self.selected_text = selected_text

    def run(self):
        try:
            # Execute search in background thread
            result = self.web_search_handler.execute_search_or_scrape(
                process_result=self.process_result,
                selected_text=self.selected_text
            )
            self.search_completed.emit(result)
        except Exception as e:
            logging.exception(f"Error in web search worker thread: {e}")
            self.search_completed.emit(
                {'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"})


class WebSearchTool:
    """A tool to perform web searches and scrape content using WebSearchHandler."""

    def __init__(self, web_search_handler: WebSearchHandler):
        """
        Initializes the WebSearchTool.

        Args:
            web_search_handler: An instance of WebSearchHandler.
        """
        # Use string comparison for class name to avoid circular import issues
        handler_class_name = web_search_handler.__class__.__name__
        if handler_class_name != 'WebSearchHandler':
            raise TypeError(
                "web_search_handler must be an instance of WebSearchHandler")
        self.web_search_handler = web_search_handler
        logging.info("WebSearchTool initialized.")

    def run(self, query: str, mode: str = 'web_search', url: Optional[str] = None, selected_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a web search or link scrape based on the provided arguments.

        Args:
            query: The search query or context for scraping.
            mode: 'web_search' or 'link_scrape'. Defaults to 'web_search'.
            url: The URL to scrape (required if mode is 'link_scrape').
            selected_text: Optional selected text context.

        Returns:
            A dictionary containing the results or an error message.
            Example success: {'status': 'success', 'data': 'Formatted results...'}
            Example error: {'status': 'error', 'message': 'Error details...'}
        """
        logging.info(
            f"WebSearchTool run called: mode={mode}, query='{query[:50]}...', url={url}")

        if mode not in ['web_search', 'link_scrape']:
            logging.error(f"Invalid mode specified for WebSearchTool: {mode}")
            return {'status': 'error', 'message': f"Invalid mode: {mode}. Must be 'web_search' or 'link_scrape'."}

        if mode == 'link_scrape' and not url:
            logging.error("URL is required for link_scrape mode.")
            return {'status': 'error', 'message': "URL parameter is required for link_scrape mode."}

        # Prepare the input dictionary for execute_search_or_scrape
        process_result = {
            'mode': mode,
            'query': query,  # The original query/context text
            'url': url,
            'original_query': query  # Keep track of original query for formatting
        }

        try:
            # Use the WebSearchHandler's execute method
            execution_result = self.web_search_handler.execute_search_or_scrape(
                process_result=process_result,
                selected_text=selected_text
            )

            # Process the result from the handler
            if execution_result.get('status') == 'success':
                # Extract the formatted query/content prepared for the LLM
                formatted_data = execution_result.get(
                    'query', 'No data returned.')
                system_instruction = execution_result.get(
                    'system_instruction')  # Optional

                # Return a structured success response
                response_data = {'status': 'success', 'data': formatted_data}
                if system_instruction:
                    response_data['system_instruction'] = system_instruction
                logging.info("WebSearchTool execution successful.")
                return response_data
            else:
                # Return a structured error response
                error_message = execution_result.get(
                    'error', 'Unknown error during web search/scrape.')
                logging.error(
                    f"WebSearchTool execution failed: {error_message}")
                return {'status': 'error', 'message': error_message}

        except Exception as e:
            logging.exception(
                f"Unexpected error during WebSearchTool execution: {e}")
            return {'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"}


# Example Usage (for testing purposes, remove or comment out in production)
if __name__ == '__main__':
    # This requires a mock or real WebSearchHandler and Settings
    # Setup basic logging for testing
    logging.basicConfig(level=logging.INFO)

    # Mock Settings and LLM Handler for WebSearchHandler initialization
    class MockSettings:
        def get(self, section, key, default=None):
            if key == 'default_provider':
                return 'ddg_search'
            if key == 'max_results':
                return 3
            return default

        def get_api_key(self, provider): return None  # No API keys for mock
        def get_selected_models(self): return []
        def load_settings(self): pass
        # Mock signal connection

        class MockSignal:
            def connect(self, slot): pass
        web_search_changed = MockSignal()

    class MockLLMHandler:
        def get_response(self, *args, **kwargs):
            # Return a dummy optimized query
            return "optimized test query"
        llm = None  # Mock LLM attribute

    try:
        # Create a WebSearchHandler instance (might need mocks if API keys/LLM are strict)
        mock_settings = MockSettings()
        mock_llm_handler = MockLLMHandler()
        web_search_handler = WebSearchHandler(llm_handler=mock_llm_handler)
        web_search_handler.settings = mock_settings  # Use mock settings
        web_search_handler.initialize_search_providers()  # Initialize with mock settings

        # Create the tool instance
        web_search_tool = WebSearchTool(web_search_handler)

        # Test web search
        print("\n--- Testing Web Search ---")
        search_result = web_search_tool.run(
            query="What is LangGraph?", mode='web_search')
        print("Search Result:", search_result)

        # Test link scrape (requires a valid URL)
        print("\n--- Testing Link Scrape ---")
        scrape_url = "https://langchain.com/"  # Example URL
        scrape_result = web_search_tool.run(
            query=f"Summarize this page: {scrape_url}", mode='link_scrape', url=scrape_url)
        print("Scrape Result:", scrape_result)

        # Test error case (invalid mode)
        print("\n--- Testing Invalid Mode ---")
        error_result = web_search_tool.run(query="test", mode='invalid_mode')
        print("Error Result:", error_result)

    except Exception as e:
        print(f"Error during example usage: {e}")
