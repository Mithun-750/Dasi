import logging
import asyncio
import time
import threading
from typing import Dict, List, Optional, Any, TypedDict, Annotated, Callable

# LangChain imports
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# Define the state structure for our graph


class GraphState(TypedDict):
    """State for the LLM processing graph."""
    # Input fields
    query: str
    session_id: str
    selected_text: Optional[str]
    mode: str
    image_data: Optional[str]
    model_name: Optional[str]

    # Processing fields
    messages: List[Any]
    use_web_search: bool
    web_search_query: Optional[str]  # Query used for web search node
    web_search_results: Optional[Dict]  # Results from web search node
    use_vision: bool
    vision_description: Optional[str]
    llm_instance: Optional[Any]  # Add field for the specific LLM instance

    # Tool calling fields
    pending_tool_call: Optional[Dict]  # Tool call requested by LLM
    # Result of a tool call after user confirmation
    tool_call_result: Optional[Dict]

    # Output fields
    response: str
    detected_language: Optional[str]


class LangGraphNodes:
    """
    Contains all node functions for the LangGraph state machine.
    This class requires a LangGraphHandler instance to be passed to the constructor.
    """

    def __init__(self, handler):
        """
        Initialize with a reference to the main handler.

        Args:
            handler: The LangGraphHandler instance that owns these nodes
        """
        self.handler = handler
        # References to services managed by the handler
        self.web_search_handler = handler.web_search_handler
        self.vision_handler = handler.vision_handler
        self.settings = handler.settings
        self.tool_call_handler = handler.tool_call_handler
        # State for tool calling
        self.tool_call_event = threading.Event()
        self.tool_call_result = None
        self.pending_llm_tool_id = None  # Add attribute to store the LLM's tool ID

        # Connect tool call completed signal
        self.tool_call_handler.tool_call_completed.connect(
            self._on_tool_call_completed)

    def initialize_state(self, state: GraphState) -> GraphState:
        """Initialize the state with defaults for any missing values."""
        # Ensure all required fields are present
        if 'session_id' not in state:
            state['session_id'] = 'default'
        if 'mode' not in state:
            state['mode'] = 'chat'
        if 'messages' not in state:
            state['messages'] = []
        if 'use_web_search' not in state:
            state['use_web_search'] = False
        if 'use_vision' not in state:
            state['use_vision'] = False
        if 'pending_tool_call' not in state:
            state['pending_tool_call'] = None
        if 'tool_call_result' not in state:
            state['tool_call_result'] = None

        return state

    def parse_query(self, state: GraphState) -> GraphState:
        """Parse query for mode, image, web search triggers, and selected text."""
        logging.info("Entering parse_query node")
        updated_state = state.copy()
        query = updated_state['query']
        image_data = updated_state.get('image_data')
        selected_text = updated_state.get('selected_text')
        logging.debug(
            f"Inside parse_query: query='{query[:50]}...', has_image_data={image_data is not None}")

        # Default flags
        updated_state['use_vision'] = bool(image_data)
        updated_state['use_web_search'] = False
        updated_state['web_search_query'] = None  # Initialize web search query

        # Let the WebSearchHandler process the query context.
        # It will determine if web search is applicable based on triggers (e.g., /web, URL)
        # and its own internal checks against settings (API keys, enabled providers).
        process_result = self.web_search_handler.process_query_context(
            query,
            {'selected_text': selected_text}
        )

        # Store the potentially processed query for the web search node
        # This might be the original query or one modified by the context processor
        updated_state['web_search_query'] = process_result['query']

        # Set the flag if the handler determined web search/scrape is needed
        if process_result['mode'] in ['web_search', 'link_scrape']:
            logging.info(
                f"Web search/scrape triggered by handler. Mode: {process_result['mode']}")
            updated_state['use_web_search'] = True
            # The actual search happens in the web_search node
            # Keep the original query in updated_state['query'] for context in later steps
            # The web_search node will use updated_state['web_search_query']
        else:
            # If web search wasn't triggered by the handler, update the main query
            # with the result from the context processor (which might have just extracted context)
            updated_state['query'] = process_result['query']

        logging.debug(
            f"Parsed query. State: use_vision={updated_state['use_vision']}, use_web_search={updated_state['use_web_search']}, web_search_query={updated_state['web_search_query']}")
        return updated_state

    def web_search(self, state: GraphState) -> GraphState:
        """Perform web search or link scraping if triggered."""
        updated_state = state.copy()
        logging.info("Entering web_search node")

        if not updated_state.get('use_web_search', False):
            logging.debug("Skipping web search - use_web_search is false.")
            # Ensure flag is false if somehow reached here erroneously
            updated_state['use_web_search'] = False
            return updated_state

        selected_text = updated_state.get('selected_text')

        # Re-run context processing using the *original* query from the state
        # to ensure we correctly identify the mode (web_search vs link_scrape)
        # and extract the URL if it's a scrape.
        process_result = self.web_search_handler.process_query_context(
            updated_state['query'],  # Use original query for context detection
            {'selected_text': selected_text}
        )

        search_mode = process_result.get('mode')
        if search_mode not in ['web_search', 'link_scrape']:
            logging.warning(
                f"Web search node entered, but mode is '{search_mode}' based on original query. Skipping search.")
            # Turn off flag if mode is wrong
            updated_state['use_web_search'] = False
            return updated_state

        logging.info(f"Executing {search_mode}...")

        # Pass the full process_result dictionary obtained above directly
        search_result = self.web_search_handler.execute_search_or_scrape(
            process_result,  # Pass the dictionary directly
            selected_text
        )

        # Store results in the state
        updated_state['web_search_results'] = search_result
        logging.debug(f"Web search/scrape execution results: {search_result}")

        return updated_state

    def vision_processing(self, state: GraphState) -> GraphState:
        """Process image data using the VisionHandler if needed."""
        updated_state = state.copy()
        logging.info("Entering vision_processing node")
        use_vis = updated_state.get('use_vision')
        has_img = updated_state.get('image_data') is not None
        logging.debug(
            f"Inside vision_processing: use_vision={use_vis}, has_image={has_img}")

        if not use_vis or not has_img:
            logging.debug(
                "Skipping vision processing - use_vision is false or no image data.")
            # Ensure flag is false if state is inconsistent
            updated_state['use_vision'] = False
            return updated_state

        try:
            logging.info("Calling VisionHandler to get visual description.")
            description = self.vision_handler.get_visual_description(
                image_data_base64=updated_state['image_data'],
                # Use original query as hint
                prompt_hint=updated_state['query']
            )

            if description:
                # Vision model processed the image and returned a description
                updated_state['vision_description'] = description
                logging.info("Vision description generated successfully.")
                # If we have a description, then the main model shouldn't get the image
                updated_state['use_vision'] = True
            else:
                # Check if vision model is not configured
                if not self.vision_handler.has_vision_model_configured():
                    logging.info(
                        "No vision model configured - passing image to main model")
                    # Keep use_vision=True so the image is passed to the main model
                    updated_state['vision_description'] = None
                else:
                    # Vision model failed to generate a description
                    logging.warning("VisionHandler returned no description.")
                    # Add a system note later in prepare_messages if description failed
                    updated_state['vision_description'] = None
        except Exception as e:
            logging.error(
                f"Error during vision processing: {str(e)}", exc_info=True)
            # Add a system note later in prepare_messages
            # Explicitly set to None
            updated_state['vision_description'] = None

        return updated_state

    def prepare_messages(self, state: GraphState) -> GraphState:
        """Prepare the messages list for the LLM, incorporating web results and vision description."""
        updated_state = state.copy()
        logging.info("Entering prepare_messages node")

        # Start with system message
        messages = [SystemMessage(content=self.handler.system_prompt)]

        # Add mode-specific instruction
        from core.prompts_hub import COMPOSE_MODE_INSTRUCTION, CHAT_MODE_INSTRUCTION
        if state['mode'] == 'compose':
            mode_instruction = COMPOSE_MODE_INSTRUCTION
        else:
            mode_instruction = CHAT_MODE_INSTRUCTION

        messages.append(SystemMessage(content=mode_instruction))

        # Add chat history
        session_id = state['session_id']
        message_history = self.handler._get_message_history(session_id)
        history_messages = message_history.messages[-self.handler.history_limit:
                                                    ] if message_history.messages else []

        # Convert to appropriate message types
        typed_history = []
        for msg in history_messages:
            if isinstance(msg, HumanMessage):
                typed_history.append(msg)
            elif isinstance(msg, AIMessage):
                typed_history.append(msg)
            elif isinstance(msg, SystemMessage):
                typed_history.append(msg)
            elif isinstance(msg, ToolMessage):
                typed_history.append(msg)  # Make sure to include ToolMessages
            elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                if msg.type == 'human':
                    typed_history.append(HumanMessage(content=msg.content))
                elif msg.type == 'ai':
                    typed_history.append(AIMessage(content=msg.content))
                elif msg.type == 'tool':
                    # Handle legacy tool messages
                    tool_call_id = getattr(msg, 'tool_call_id', None)
                    typed_history.append(ToolMessage(
                        content=msg.content, tool_call_id=tool_call_id))

        messages.extend(typed_history)

        # Handle Tool Call Results
        # If there's a tool call result from user confirmation, add a ToolMessage to the messages
        tool_call_result = state.get('tool_call_result')
        if tool_call_result and isinstance(tool_call_result, dict):
            logging.info(
                f"Adding tool call result to messages: {tool_call_result}")
            tool_name = tool_call_result.get('tool', 'unknown')
            result = tool_call_result.get('result', {})
            # Get the tool call ID if present
            tool_call_id = tool_call_result.get('id')

            if result == 'rejected':
                # For rejected tool calls, add a special ToolMessage indicating rejection
                # This provides explicit feedback to the model about the rejection
                messages.append(ToolMessage(
                    content="The user rejected this tool call request. Please proceed without using this tool.",
                    tool_call_id=tool_call_id
                ))
                logging.info("Added tool rejection message")
            else:
                # For successful tool calls:
                if tool_name == 'web_search' and isinstance(result, dict) and result.get('status') == 'success':
                    # Format web search results as a structured ToolMessage
                    tool_content = result.get('data', 'No results found')
                    messages.append(ToolMessage(
                        content=tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added web search ToolMessage with ID: {tool_call_id}")
                elif tool_name == 'system_info' and isinstance(result, dict) and result.get('status') == 'success':
                    # Format system info results
                    tool_content = result.get(
                        'data', 'No system information available')
                    messages.append(ToolMessage(
                        content=tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added system info ToolMessage with ID: {tool_call_id}")
                else:
                    # Generic format for other tools or error cases
                    if isinstance(result, dict) and 'data' in result:
                        tool_content = result.get('data')
                    elif isinstance(result, dict) and 'status' in result and 'data' in result:
                        tool_content = result.get('data')
                    else:
                        # Try to extract useful information from nested structures
                        if isinstance(result, dict) and 'result' in result and isinstance(result['result'], dict):
                            inner_result = result['result']
                            if 'data' in inner_result:
                                tool_content = inner_result['data']
                            elif 'status' in inner_result and inner_result.get('status') == 'success':
                                tool_content = str(inner_result)
                            else:
                                tool_content = str(result)
                        else:
                            tool_content = str(result)

                    # Format the tool content for better readability
                    try:
                        # If it's already a string, we're good
                        if isinstance(tool_content, str):
                            formatted_content = tool_content
                        # If it's a dict or list, format it nicely as JSON with indentation
                        elif isinstance(tool_content, (dict, list)):
                            import json
                            formatted_content = json.dumps(
                                tool_content, indent=2)
                        else:
                            # For any other type, use string representation
                            formatted_content = str(tool_content)

                        # Add a title to help the LLM understand what this tool result is
                        final_tool_content = f"Result from {tool_name} tool:\n\n{formatted_content}"
                    except Exception as e:
                        logging.warning(f"Error formatting tool content: {e}")
                        final_tool_content = str(tool_content)

                    messages.append(ToolMessage(
                        content=final_tool_content, tool_call_id=tool_call_id))
                    logging.info(
                        f"Added generic ToolMessage for {tool_name} with ID: {tool_call_id}")
                    logging.debug(f"Tool content: {final_tool_content[:200]}..." if len(
                        str(final_tool_content)) > 200 else final_tool_content)

                # Add a system instruction to analyze the tool result
                messages.append(SystemMessage(
                    content=f"This is the result of the {tool_name} tool call you requested. Incorporate this information into your response to the user."
                ))
                logging.info(
                    f"Added system instruction for {tool_name} tool result")

            # Clear the tool call result after using it to prevent reprocessing
            updated_state['tool_call_result'] = None

        # Handle web search results (separate from tool calls)
        web_search_results = state.get('web_search_results')
        final_query_text = updated_state['query']  # Start with original query

        # Existing web search results handling
        if web_search_results:
            logging.info(
                "Incorporating web search/scrape results into messages.")
            if web_search_results.get('status') == 'error':
                logging.error(
                    f"Web search/scrape failed: {web_search_results.get('error')}")
                # Modify query to inform LLM about the error
                search_mode_desc = web_search_results.get(
                    'mode', 'web task').replace('_', ' ')  # Use a generic term
                error_info = web_search_results.get('error', 'Unknown error')
                # The query before web node modified it
                original_query = updated_state['query']
                final_query_text = f"I tried to perform a {search_mode_desc} based on the query '{original_query}' but encountered an error: {error_info}. Please answer the original query '{original_query}' without the web results."
            elif web_search_results.get('status') == 'success':
                # Use the fully formatted query from the web_search_handler
                if 'query' in web_search_results:
                    final_query_text = web_search_results['query']
                    logging.debug(
                        "Using pre-formatted query from web_search_handler.")
                else:
                    logging.warning(
                        "Web search results status is success, but 'query' key is missing. Using original query.")

                # Add system instruction from web_search_handler if it exists
                if web_search_results.get('system_instruction'):
                    messages.append(SystemMessage(
                        content=web_search_results['system_instruction']))
                    logging.debug(
                        "Added system instruction from web_search_handler.")
            else:
                logging.warning(
                    f"Web search results present but status is not 'success' or 'error': {web_search_results.get('status')}")
                # Fallback to original query if status is unexpected

        # Append selected text if present AND not already added via web blocks
        if state.get('selected_text') and "=====SELECTED_TEXT=====" not in final_query_text:
            final_query_text += f"\n\n=====SELECTED_TEXT=====<text selected by the user>\n{state['selected_text']}\n======================="

        # Determine final message type based on image and vision description
        image_data = state.get('image_data')
        vision_description = state.get('vision_description')
        is_vision_model_configured = self.vision_handler.has_vision_model_configured()

        if vision_description:
            # Case 1: Vision model success - Append description, send text-only
            logging.info(
                "Vision description present. Appending to text query.")
            final_query_content = f"{final_query_text}\n\n=====VISUAL_DESCRIPTION=====<description generated by vision model>\n{vision_description}\n======================="
            query_message = HumanMessage(content=final_query_content)

        elif image_data:
            # Image present, but no description generated
            if is_vision_model_configured:
                # Case 3: Vision model configured but failed - Send text-only with error note
                logging.warning(
                    "Image present, vision model configured but failed. Adding system note.")
                final_query_content = f"{final_query_text}\n\n=====SYSTEM_NOTE=====\n(Failed to process the provided visual input using the configured vision model.)\n====================="
                query_message = HumanMessage(content=final_query_content)
            else:
                # Case 2: No vision model configured - Send multimodal message
                logging.info(
                    "Image present, no vision model configured. Constructing multimodal message.")
                # Clean base64 data
                if image_data.startswith('data:'):
                    image_data = image_data.split(',', 1)[-1]
                content_blocks = [
                    {"type": "text", "text": final_query_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"}
                    }
                ]
                query_message = HumanMessage(content=content_blocks)
        else:
            # Case 4: No image data - Send text-only
            logging.info("No image data. Constructing text-only message.")
            query_message = HumanMessage(content=final_query_text)

        # Add the final prepared query message to the list
        messages.append(query_message)

        # Save the prepared messages
        updated_state['messages'] = messages
        logging.debug(f"Prepared messages: {messages}")

        return updated_state

    def generate_response(self, state: GraphState) -> GraphState:
        """Generate a response using the LLM. If a tool call is detected, add it to state and route to tool_call node."""
        updated_state = state.copy()
        llm_instance = state.get('llm_instance')
        try:
            if not llm_instance:
                if not self.handler.llm:
                    if not self.handler.initialize_llm(model_name=state.get('model_name')):
                        updated_state['response'] = "⚠️ LLM could not be initialized from state or fallback."
                        return updated_state
                    llm_instance = self.handler.llm
                else:
                    llm_instance = self.handler.llm

            logging.info("Invoking LLM for response generation")
            response = llm_instance.invoke(state['messages'])
            final_response = response.content.strip()

            # Log the full response for debugging
            logging.debug(f"LLM raw response: {final_response[:200]}..." if len(
                final_response) > 200 else final_response)

            # Improved tool call detection - check for both marker format and function calling if available
            tool_detected = False
            tool_name = None
            tool_args = None
            tool_id = None

            # Check for the custom tool marker format
            if '<<TOOL:' in final_response:
                logging.info("Tool call marker detected in LLM response")
                import json
                import re
                import uuid

                match = re.search(
                    r'<<TOOL:\s*(\w+)\s*(\{.*?\})>>', final_response)
                if match:
                    tool_detected = True
                    tool_name = match.group(1)
                    tool_args_str = match.group(2)
                    logging.info(
                        f"Parsed tool call: {tool_name} with args: {tool_args_str}")
                    try:
                        tool_args = json.loads(tool_args_str)
                        # Generate a unique ID for this tool call if none exists
                        tool_id = f"call_{uuid.uuid4().hex[:24]}"
                        # Clean the response by removing the tool call marker
                        cleaned_response = re.sub(
                            r'<<TOOL:.*?>>', '', final_response).strip()
                        final_response = cleaned_response
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing tool args JSON: {e}")
                        tool_detected = False
                else:
                    logging.warning(
                        "Tool call marker found but couldn't parse the format")

            # Check for function calling in OpenAI/Anthropic response format if available
            # This is model-dependent and would need to be expanded for each supported model's format
            elif hasattr(response, 'additional_kwargs') and response.additional_kwargs:
                # OpenAI format
                if 'function_call' in response.additional_kwargs:
                    func_call = response.additional_kwargs['function_call']
                    if isinstance(func_call, dict) and 'name' in func_call and 'arguments' in func_call:
                        tool_detected = True
                        tool_name = func_call['name']
                        try:
                            import json
                            tool_args = json.loads(func_call['arguments'])
                            tool_id = func_call.get('id')
                            if not tool_id:
                                import uuid
                                tool_id = f"call_{uuid.uuid4().hex[:24]}"
                            logging.info(
                                f"Detected OpenAI function call: {tool_name}, id: {tool_id}")
                        except json.JSONDecodeError:
                            logging.error(
                                f"Error parsing OpenAI function args JSON")
                            tool_detected = False

                # Anthropic format (tool_use)
                elif 'tool_use' in response.additional_kwargs:
                    tool_use = response.additional_kwargs['tool_use']
                    if isinstance(tool_use, dict) and 'name' in tool_use and 'input' in tool_use:
                        tool_detected = True
                        tool_name = tool_use['name']
                        # Already a dict in Anthropic's format
                        tool_args = tool_use['input']
                        tool_id = tool_use.get('id')
                        if not tool_id:
                            import uuid
                            tool_id = f"call_{uuid.uuid4().hex[:24]}"
                        logging.info(
                            f"Detected Anthropic tool_use: {tool_name}, id: {tool_id}")

                # Check for tool_calls array (newer format like OpenAI API)
                elif 'tool_calls' in response.additional_kwargs:
                    tool_calls = response.additional_kwargs['tool_calls']
                    if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                        first_call = tool_calls[0]
                        if isinstance(first_call, dict):
                            # Extract from potential nested structure
                            if 'function' in first_call and isinstance(first_call['function'], dict):
                                tool_detected = True
                                tool_name = first_call['function'].get('name')
                                try:
                                    import json
                                    args_str = first_call['function'].get(
                                        'arguments', '{}')
                                    tool_args = json.loads(args_str)
                                    tool_id = first_call.get('id')
                                    if not tool_id:
                                        import uuid
                                        tool_id = f"call_{uuid.uuid4().hex[:24]}"
                                    logging.info(
                                        f"Detected tool_calls array: {tool_name}, id: {tool_id}")
                                except json.JSONDecodeError:
                                    logging.error(
                                        f"Error parsing tool_calls args JSON")
                                    tool_detected = False
                            else:
                                # Direct structure
                                tool_detected = True
                                tool_name = first_call.get('name')
                                tool_args = first_call.get('args', {})
                                tool_id = first_call.get('id')
                                if not tool_id:
                                    import uuid
                                    tool_id = f"call_{uuid.uuid4().hex[:24]}"
                                logging.info(
                                    f"Detected direct tool_calls: {tool_name}, id: {tool_id}")

            if tool_detected and tool_name and tool_args is not None:
                # Add the tool call to state and let the graph handle routing
                updated_state['pending_tool_call'] = {
                    'tool': tool_name,
                    'args': tool_args,
                    'id': tool_id  # Include the tool ID
                }
                updated_state['response'] = final_response
                logging.info(
                    f"Tool call for {tool_name} (ID: {tool_id}) added to state, routing to tool_call node")
                return updated_state
            else:
                logging.debug("No tool calls detected in response")

            # Normal response processing (non-tool call)
            is_compose_mode = (state['mode'] == 'compose')
            if is_compose_mode:
                final_response, detected_language = self.handler._extract_code_block(
                    final_response)
                updated_state['detected_language'] = detected_language
            session_id = state['session_id']
            message_history = self.handler._get_message_history(session_id)
            message_history.add_message(state['messages'][-1])
            message_history.add_message(AIMessage(content=final_response))
            updated_state['response'] = final_response
            return updated_state
        except Exception as e:
            logging.error(
                f"Error getting LLM response in generate_response node: {str(e)}", exc_info=True)
            error_msg = str(e)
            updated_state['response'] = f"⚠️ Error in generate_response: {error_msg}"
            return updated_state

    async def tool_call_node(self, state):
        """
        LangGraph node for tool calling with user confirmation.

        This node:
        1. Takes a tool call request from the LLM
        2. Sends it to the ToolCallHandler for user confirmation
        3. Waits for user response (accept/reject)
        4. Receives the tool result
        5. Updates the state with the result
        6. Routes back to prepare_messages
        """
        # Get the pending tool call
        tool_call = state.get('pending_tool_call')
        if not tool_call:
            logging.warning(
                "tool_call_node entered without a pending_tool_call in state")
            return state

        tool_name = tool_call.get('tool')
        tool_args = tool_call.get('args', {})
        # The tool call ID for proper response association
        tool_id = tool_call.get('id')

        logging.info(
            f"Tool call node processing: {tool_name} with ID: {tool_id}")

        # Clear the pending tool call from state to prevent reprocessing
        new_state = state.copy()
        new_state['pending_tool_call'] = None

        try:
            # Emit to UI and wait for user confirmation
            self.tool_call_handler.request_tool_call(tool_name, tool_args)
            self.tool_call_event.clear()

            # Log the start of waiting period
            wait_start_time = time.monotonic()
            logging.info(f"Waiting for user to confirm tool call: {tool_name}")

            # Update the UI callback if available to show we're waiting
            callback = None  # Define callback to avoid reference errors
            accumulated_response = ""
            # TODO: Get callback and current accumulated response if possible
            if 'response' in state:
                accumulated_response = state['response']

            if callback:
                callback(accumulated_response +
                         "\n\n[Waiting for your confirmation to use the tool...]")

            # Wait for user response with periodic progress updates
            logging.info(
                f"Waiting for user response for {tool_name} tool call")
            try:
                # Run the blocking threading.Event.wait() in a separate thread
                # to avoid blocking the main asyncio event loop.
                loop = asyncio.get_running_loop()
                tool_call_timeout = 120.0

                if callback:
                    # If we have a callback, we need to periodically check
                    wait_start = time.monotonic()
                    while True:
                        # Wait for 1 second in executor
                        event_set = await loop.run_in_executor(
                            None, self.tool_call_event.wait, 1.0
                        )
                        if event_set:
                            break  # Event was set

                        # Check for timeout
                        wait_duration = time.monotonic() - wait_start
                        if wait_duration >= tool_call_timeout:
                            logging.warning(
                                f"Timeout waiting for tool call response for {tool_name}")
                            # Set result to timeout error
                            self.tool_call_result = {
                                'tool': tool_name,
                                'id': tool_id,
                                'result': {
                                    'status': 'error',
                                    'message': 'Timeout waiting for user confirmation'
                                }
                            }
                            break  # Exit loop on timeout

                        # Update dots for UI callback
                        dots = "." * (int(wait_duration) % 4)
                        waiting_message = f"{accumulated_response}\n\n[Waiting for your confirmation to use the tool{dots}]"
                        callback(waiting_message)
                else:
                    # If no callback, just wait directly in executor
                    event_set = await loop.run_in_executor(
                        None, self.tool_call_event.wait, tool_call_timeout
                    )
                    if not event_set:
                        logging.warning(
                            f"Timeout waiting for tool call response for {tool_name}")
                        # Set result to timeout error
                        self.tool_call_result = {
                            'tool': tool_name,
                            'id': tool_id,
                            'result': {
                                'status': 'error',
                                'message': 'Timeout waiting for user confirmation'
                            }
                        }

                wait_end_time = time.monotonic()
                wait_duration = wait_end_time - wait_start_time
                logging.info(
                    f"Received user response for {tool_name} tool call after {wait_duration:.3f} seconds")

            except Exception as e:
                logging.error(
                    f"Error during tool call wait: {e}", exc_info=True)
                # Set result to error
                self.tool_call_result = {
                    'tool': tool_name,
                    'id': tool_id,
                    'result': {
                        'status': 'error',
                        'message': f'Error waiting for response: {str(e)}'
                    }
                }

            # Clear the event for the next tool call
            self.tool_call_event.clear()

            # Get the result
            result = self.tool_call_result

            # Add the tool_call_id to the result for proper association
            if result and isinstance(result, dict):
                if 'id' not in result:
                    result['id'] = tool_id

                # Ensure the tool name is present
                if 'tool' not in result:
                    result['tool'] = tool_name

                # Enrich the result with metadata to aid the LLM in understanding the tool context
                if result.get('result') != 'rejected' and 'metadata' not in result:
                    result['metadata'] = {
                        'tool_description': self.tool_call_handler.get_tool_description(tool_name),
                        'timestamp': time.time()
                    }

            # Store the result in the state for prepare_messages to process
            new_state['tool_call_result'] = result
            logging.info(f"Tool call result added to state: {result}")

            # Reset the tool_call_result to avoid reuse
            self.tool_call_result = None

            # Notify the UI that we're about to process the tool results with the LLM
            # This helps ensure the preview panel is visible for the follow-up response
            try:
                # First signal processing is starting
                self.tool_call_handler.tool_call_processing.emit(tool_name)

                # Then after a short delay, signal it's complete to transition UI
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(200, lambda: self.tool_call_handler.tool_call_completed.emit({
                    "tool": tool_name,
                    "id": tool_id,
                    "result": "processed",  # Special flag to indicate UI should update
                }))
            except Exception as e:
                logging.error(
                    f"Error emitting tool_call_processing signal: {e}")

        except Exception as e:
            logging.error(f"Error in tool_call_node: {e}", exc_info=True)
            # Add error result to state
            new_state['tool_call_result'] = {
                'tool': tool_name,
                'result': {
                    'status': 'error',
                    'message': f"Error during tool execution: {str(e)}"
                },
                'id': tool_id
            }

        return new_state

    def _on_tool_call_completed(self, result):
        """Slot method called when ToolCallHandler emits tool_call_completed signal."""
        logging.info(f"Tool call completed with internal result: {result}")

        # Use the stored LLM tool ID if available, otherwise keep internal ID as fallback
        if self.pending_llm_tool_id:
            logging.info(
                f"Replacing internal ID '{result.get('id')}' with stored LLM tool ID '{self.pending_llm_tool_id}'")
            result['id'] = self.pending_llm_tool_id
            self.pending_llm_tool_id = None  # Clear the stored ID
        else:
            logging.warning(
                "No pending LLM tool ID found when tool completed. Using internal ID.")

        # Store the (potentially updated) result
        self.tool_call_result = result
        logging.info(f"Final tool_call_result set to: {self.tool_call_result}")

        # Set the event to signal that the result is ready
        try:
            self.tool_call_event.set()
            logging.info("Tool call event set successfully")
        except Exception as e:
            logging.error(f"Error setting tool call event: {e}", exc_info=True)
