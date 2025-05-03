import logging
import asyncio
import time
import re
import json
from typing import Optional, Callable, Dict, Any, List

# LangChain imports
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage

from PyQt6.QtCore import QTimer


class ResponseGenerator:
    """
    Handles response generation and streaming for the LangGraphHandler.
    This class requires a LangGraphHandler instance to be passed to the constructor.
    """

    def __init__(self, handler):
        """
        Initialize with a reference to the main handler.

        Args:
            handler: The LangGraphHandler instance that owns this generator
        """
        self.handler = handler
        self.detected_language = None

    def _extract_code_block(self, response: str):
        """Extract code blocks from response text."""
        # Strip whitespace for more reliable pattern matching
        stripped_response = response.strip()

        # Check if response starts with triple backticks and ends with triple backticks
        if stripped_response.startswith("```") and stripped_response.endswith("```"):
            # Find the first newline to extract language
            first_line_end = stripped_response.find("\n")
            if first_line_end > 3:  # We have a language identifier
                language = stripped_response[3:first_line_end].strip().lower()
                # Remove the starting line with backticks and language
                content = stripped_response[first_line_end+1:-3].strip()
                return content, language
            else:
                # No language specified
                content = stripped_response[4:-3].strip()
                return content, None

        # Fallback to regex for more complex patterns
        code_block_pattern = r'^\s*```(\w*)\s*\n([\s\S]*?)\n\s*```\s*$'
        match = re.match(code_block_pattern, stripped_response)

        if match:
            language = match.group(1).strip().lower() or None
            code_content = match.group(2)
            return code_content, language

        # If we get here, it wasn't a code block or the pattern didn't match
        return response, None

    async def get_response_async(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None,
                                 session_id: str = "default", selected_text: str = None,
                                 mode: str = "chat", image_data: Optional[str] = None) -> str:
        """
        Process a query asynchronously using the LangGraph application and stream the response.

        Args:
            query: The user's query.
            callback: Optional callback function to receive streamed chunks.
            model: Optional specific model ID to use.
            session_id: The session ID for maintaining chat history.
            selected_text: Optional selected text from the user's environment.
            mode: The interaction mode ("chat" or "compose").
            image_data: Optional base64 encoded image data for vision models.

        Returns:
            The complete response string.
        """
        try:
            logging.info(
                f"get_response_async called: model={model}, session_id={session_id}, mode={mode}, has_image_data={image_data is not None}")
            if image_data:
                logging.debug(
                    f"Image data received (first 50 chars): {image_data[:50]}...")

            loop = asyncio.get_event_loop()  # Get the current event loop
            logging.info(
                f"get_response_async called with model: {model}, session_id: {session_id}, mode: {mode}")

            # --- Initialize LLM based on model (or default) ---
            if model:
                selected_models = self.handler.settings.get_selected_models()
                model_info = next(
                    (m for m in selected_models if m.get('id') == model), None)
                if not model_info:
                    logging.error(
                        f"Model '{model}' not found. Falling back to default.")
                    # Fallback to default if specific model not found/initialized
                    if not self.handler.initialize_llm():
                        raise ValueError("Failed to initialize default LLM.")
                else:
                    if not self.handler.initialize_llm(model_name=model, model_info=model_info):
                        raise ValueError(
                            f"Failed to initialize LLM for model: {model}")
            elif not self.handler.llm:  # Initialize default if no LLM exists
                if not self.handler.initialize_llm():
                    raise ValueError(
                        "LLM is not initialized and default failed.")
            # --- LLM Initialization END ---

            # Import GraphState from langgraph_nodes
            from core.langgraph_nodes import GraphState

            # Prepare initial state
            initial_state = GraphState(
                query=query,
                session_id=session_id,
                selected_text=selected_text,
                mode=mode,
                image_data=image_data,
                model_name=model if model else getattr(self.handler.llm, 'model_name', None) or getattr(
                    self.handler.llm, 'model', 'unknown'),  # Use actual model name
                messages=[],
                use_web_search=False,
                web_search_query=None,
                web_search_results=None,
                use_vision=bool(image_data),
                vision_description=None,
                llm_instance=self.handler.llm,  # Pass the initialized LLM instance
                response="",
                detected_language=None,
                pending_tool_call=None,
                tool_call_result=None
            )

            # Prepare configuration for the specific session
            config = {"configurable": {"session_id": session_id}}

            # Direct approach: Run the state through the necessary nodes to prepare the messages,
            # then manually invoke the LLM with streaming rather than relying on LangGraph streaming

            # Get reference to graph nodes
            nodes = self.handler.graph_nodes

            # First process the state through all the nodes up to the LLM call
            # This is a simplified version of what the graph would do
            logging.info("Processing initial state through graph nodes")
            state = nodes.initialize_state(initial_state)
            state = nodes.parse_query(state)

            if state.get('use_web_search', False):
                state = nodes.web_search(state)

            if state.get('use_vision', False) and state.get('image_data') is not None:
                state = nodes.vision_processing(state)

            state = nodes.prepare_messages(state)

            # At this point, state['messages'] contains all the necessary messages for the LLM

            if not state.get('messages'):
                raise ValueError("No messages prepared for LLM")

            logging.info(f"Prepared {len(state['messages'])} messages for LLM")

            # Now directly call the LLM with streaming
            llm_instance = state.get('llm_instance') or self.handler.llm

            if not llm_instance:
                raise ValueError("No LLM instance available")

            logging.info(f"Invoking LLM ({model or 'default'}) with streaming")

            # Send a small initial chunk to signal the stream is starting
            if callback:
                callback("")

            # Use LangChain's streaming capability directly in a loop for multi-turn tool calls
            final_response_content = ""
            last_ai_message = None  # Store the last complete AI message object

            # Add initial HumanMessage to history
            message_history = self.handler._get_message_history(session_id)
            if state['messages'] and isinstance(state['messages'][-1], HumanMessage):
                message_history.add_message(state['messages'][-1])

            while True:  # Loop for potential multiple tool calls
                accumulated_response_this_turn = ""
                accumulated_chunk = None
                detected_tool_calls = []
                tool_call_info = None  # Store info about the tool call requested in this turn

                logging.info(
                    f"Starting LLM stream loop iteration. Current messages count: {len(state['messages'])}")
                async for chunk in llm_instance.astream(state['messages']):
                    # Accumulate the chunk object itself for tool call detection
                    if accumulated_chunk is None:
                        accumulated_chunk = chunk
                    else:
                        accumulated_chunk = accumulated_chunk + chunk

                    # Extract content for display/callback
                    chunk_content = chunk.content if hasattr(
                        chunk, 'content') else ""
                    accumulated_response_this_turn += chunk_content
                    # Keep track of the *complete* message object
                    last_ai_message = accumulated_chunk

                    # Check for tool calls (use the accumulated_chunk)
                    # Standard LangChain `tool_calls` (list of dicts)
                    if hasattr(accumulated_chunk, 'tool_calls') and accumulated_chunk.tool_calls:
                        logging.info(
                            f"Detected tool_calls: {accumulated_chunk.tool_calls}")
                        detected_tool_calls = accumulated_chunk.tool_calls
                        # Stop processing stream for this turn if tool call is detected
                        break
                    # Fallback for streaming `tool_call_chunks` (list of dicts)
                    elif hasattr(accumulated_chunk, 'tool_call_chunks') and accumulated_chunk.tool_call_chunks:
                        logging.info(
                            f"Detected tool_call_chunks: {accumulated_chunk.tool_call_chunks}")
                        # We need to assemble the full tool call info from chunks if possible,
                        # but for simplicity now, just mark that a tool is requested.
                        # The final `accumulated_chunk.tool_calls` should ideally contain the full info.
                        # For now, let's assume the last chunk will have the full `tool_calls`.
                        # If the very last chunk has `tool_calls`, the outer check will catch it.
                        pass  # Continue streaming until tool_calls is populated or stream ends

                    # Callback with the *cumulative* response so far
                    if callback:
                        try:
                            # Combine the final response from previous turns with the current turn's progress
                            callback(final_response_content +
                                     accumulated_response_this_turn)
                        except Exception as e:
                            logging.error(f"Error in streaming callback: {e}")

                # --- End of inner stream loop ---

                # Add the text content generated in this turn *before* any potential tool call
                final_response_content += accumulated_response_this_turn

                # Now, check if tool calls were detected *in the complete message* for this turn
                if last_ai_message and hasattr(last_ai_message, 'tool_calls') and last_ai_message.tool_calls:
                    detected_tool_calls = last_ai_message.tool_calls
                    logging.info(
                        f"Processing detected tool calls after stream: {detected_tool_calls}")

                    # Add the AI message *that requested the tool call* to history
                    message_history.add_message(last_ai_message)

                    # --- Process Tool Call ---
                    # TODO: Handle multiple tool calls in parallel? For now, process the first one.
                    tool_call = detected_tool_calls[0]
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args')
                    tool_id = tool_call.get('id')  # CRUCIAL for ToolMessage

                    if not tool_id:
                        logging.error(
                            f"Tool call detected for '{tool_name}' but missing 'id'. Cannot proceed.")
                        final_response_content += f"\n\n[Error: Tool call for {tool_name} missing required ID.]"
                        break  # Exit the while loop on error

                    if tool_name and tool_args is not None:
                        logging.info(
                            f"Requesting confirmation for tool call: {tool_name} (ID: {tool_id})")

                        # Store the LLM's tool_id before requesting confirmation
                        self.handler.graph_nodes.pending_llm_tool_id = tool_id

                        try:
                            # Request confirmation and wait for result
                            self.handler.tool_call_handler.request_tool_call(
                                tool_name, tool_args)
                            nodes.tool_call_event.clear()

                            # Update UI callback
                            if callback:
                                callback(
                                    final_response_content + f"\n\n[Waiting for your confirmation to use the '{tool_name}' tool...]")

                            # --- Wait for user response ---
                            logging.info(
                                f"Waiting for user response for {tool_name} (ID: {tool_id})")
                            # Simplified wait logic (reuse existing complex logic if needed)
                            loop = asyncio.get_running_loop()
                            tool_call_timeout = 120.0
                            try:
                                event_set = await loop.run_in_executor(
                                    None, nodes.tool_call_event.wait, tool_call_timeout
                                )
                                if not event_set:
                                    logging.warning(
                                        f"Timeout waiting for tool call response for {tool_name}")
                                    nodes.tool_call_result = {'tool': tool_name, 'id': tool_id, 'result': {
                                        'status': 'error', 'message': 'Timeout waiting for user confirmation'}}
                                else:
                                    logging.info(
                                        f"Received user response for {tool_name}")

                            except Exception as e:
                                logging.error(
                                    f"Error during tool call wait: {e}", exc_info=True)
                                nodes.tool_call_result = {'tool': tool_name, 'id': tool_id, 'result': {
                                    'status': 'error', 'message': f'Error waiting for response: {str(e)}'}}

                            # --- Process result ---
                            result = nodes.tool_call_result
                            nodes.tool_call_event.clear()  # Clear event after getting result

                            # Ensure result dict has the tool_id for matching
                            if result and isinstance(result, dict) and 'id' not in result:
                                # Associate result with the call
                                result['id'] = tool_id

                            if result and result.get('id') == tool_id and result.get('result') != 'rejected':
                                logging.info(
                                    f"Tool call {tool_name} (ID: {tool_id}) approved and executed.")
                                tool_content = "Tool execution failed or returned no data."
                                if isinstance(result.get('result'), dict):
                                    if result['result'].get('status') == 'error':
                                        tool_content = f"Error executing tool: {result['result'].get('message', 'Unknown error')}"
                                    elif result['result'].get('status') == 'disabled':
                                        # Handle disabled tools specially
                                        tool_content = f"The requested tool '{tool_name}' is currently disabled. {result['result'].get('message', '')}"
                                    else:
                                        # Attempt to format data nicely
                                        data = result['result'].get('data')
                                        try:
                                            if isinstance(data, (dict, list)):
                                                tool_content = json.dumps(
                                                    data, indent=2)
                                            elif data is not None:
                                                tool_content = str(data)
                                            else:
                                                tool_content = "Tool executed successfully but returned no specific data."
                                        except Exception as format_e:
                                            logging.warning(
                                                f"Could not format tool result: {format_e}")
                                            tool_content = str(data)
                                elif isinstance(result.get('result'), str):
                                    # Handle simple string results
                                    tool_content = result['result']

                                # Create ToolMessage using the correct tool_call_id
                                tool_message = ToolMessage(
                                    content=tool_content, tool_call_id=tool_id)

                                state['messages'].append(tool_message)
                                message_history.add_message(tool_message)

                                # ---> Rebuild messages from history for the next turn <--- START
                                logging.info(
                                    "Rebuilding message list from history for next LLM turn.")
                                current_history = self.handler._get_message_history(
                                    session_id)
                                rebuilt_messages = []
                                # Start with system message(s)
                                # Assuming the first message(s) in the initial state['messages'] were system messages
                                system_msgs = [
                                    m for m in state['messages'] if isinstance(m, SystemMessage)]
                                rebuilt_messages.extend(system_msgs)
                                # Add messages from DB history
                                rebuilt_messages.extend(
                                    current_history.messages)
                                # Update the state for the next loop
                                state['messages'] = rebuilt_messages
                                logging.info(
                                    f"Rebuilt messages list now has {len(state['messages'])} messages.")
                                # ---> Rebuild messages from history for the next turn <--- END

                                # Update UI (optional)
                                if callback:
                                    callback(
                                        final_response_content + f"\n\n[Processed '{tool_name}' tool result. Asking AI to continue...]")
                                await asyncio.sleep(0.1)  # Small delay

                                # Reset for the next loop iteration - IMPORTANT: We continue the loop!
                                nodes.tool_call_result = None
                                continue  # Continue the while loop to call LLM again with rejection context

                            else:
                                # Tool rejected or failed execution matching ID
                                rejection_reason = "rejected by user" if result and result.get(
                                    'result') == 'rejected' else f"failed ({result.get('result', {}).get('message', 'unknown reason')})" if result else "failed (no result)"
                                logging.warning(
                                    f"Tool call {tool_name} (ID: {tool_id}) was {rejection_reason}.")
                                final_response_content += f"\n\n[Tool call '{tool_name}' {rejection_reason}.]"
                                # Add a ToolMessage indicating rejection/failure? Or just let the loop break?
                                # Let's add a message for clarity in history.
                                tool_message = ToolMessage(
                                    content=f"Tool call {tool_name} {rejection_reason}.", tool_call_id=tool_id)
                                # Keep state consistent
                                state['messages'].append(tool_message)
                                message_history.add_message(tool_message)

                                # Add system message to explicitly instruct the LLM to proceed without the tool
                                system_instruction = SystemMessage(
                                    content=f"The user has rejected the '{tool_name}' tool request. Please acknowledge this and continue the conversation without using this tool."
                                )
                                state['messages'].append(system_instruction)
                                message_history.add_message(system_instruction)

                                # Update UI (optional)
                                if callback:
                                    callback(
                                        final_response_content + f"\n\n[The '{tool_name}' tool request was {rejection_reason}. Asking AI to continue...]")
                                await asyncio.sleep(0.1)  # Small delay

                                # Reset for the next loop iteration - IMPORTANT: We continue the loop!
                                nodes.tool_call_result = None
                                continue  # Continue the while loop to call LLM again with rejection context

                        except Exception as e:
                            logging.error(
                                f"Error processing tool call {tool_name} (ID: {tool_id}): {e}", exc_info=True)
                            final_response_content += f"\n\n[Error processing tool call '{tool_name}'.]"
                            # Add error tool message
                            tool_message = ToolMessage(
                                content=f"Error processing tool call {tool_name}: {str(e)}", tool_call_id=tool_id)
                            state['messages'].append(tool_message)
                            message_history.add_message(tool_message)
                            break  # Exit loop on error
                    else:
                        logging.error(
                            f"Detected tool call missing name or args: {tool_call}. Cannot process.")
                        final_response_content += "\n\n[Error: Invalid tool call detected.]"
                        break  # Exit loop
                else:
                    # If no tool calls detected, the conversation turn is over.
                    logging.info(
                        "No tool call detected in the final response chunk. Exiting loop.")
                    # Add the final AI message (without tool call request) to history
                    if last_ai_message:
                        message_history.add_message(last_ai_message)
                    break  # Exit the while True loop

            # --- End of while True loop ---

            logging.info(
                f"LLM interaction loop finished. Final response length: {len(final_response_content)}")

            # Explicitly signal completion via callback *after* the loop finishes
            if callback:
                logging.debug("Sending <COMPLETE> signal via callback.")
                try:
                    callback("<COMPLETE>")
                except Exception as cb_err:
                    logging.error(
                        f"Error during <COMPLETE> callback: {cb_err}")

            # Return the final assembled response
            return final_response_content

        except RuntimeError as e:
            # Catch the specific loop error
            if "attached to a different loop" in str(e):
                logging.error(
                    f"Caught asyncio loop error: {e}. This might indicate an issue with nest_asyncio or thread interaction.")
                # Potentially re-raise or handle differently if needed
                raise e  # Re-raise for now
            else:
                logging.error(f"Runtime error during async response: {e}")
                raise e
        except Exception as e:
            logging.exception(
                f"Error during async LLM stream for session {session_id}: {e}")
            # Ensure callback is called with error if provided
            if callback:
                try:
                    callback(f"Error: {e}")
                except Exception as cb_err:
                    logging.error(
                        f"Error calling callback with error message: {cb_err}")
            raise  # Re-raise the exception after logging

    def get_response(self, query: str, callback: Optional[Callable[[str], None]] = None, model: Optional[str] = None,
                     session_id: str = "default", selected_text: str = None,
                     mode: str = "chat", image_data: Optional[str] = None) -> str:
        """Synchronous wrapper for get_response_async."""
        try:
            # Get the current running event loop or create a new one if none exists
            # This is important when calling from a synchronous context (like Qt signal handlers)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If a loop is already running (e.g., from nest_asyncio), create a future
                # and run the coroutine within that loop.
                future = asyncio.ensure_future(
                    self.get_response_async(
                        query, callback, model, session_id, selected_text, mode, image_data)
                )
                # This part is tricky. Blocking here might freeze the UI if called from the main thread.
                # Consider running this in a separate thread if blocking is an issue.
                # For now, let's assume nest_asyncio handles the blocking correctly.
                return loop.run_until_complete(future)
            else:
                # If no loop is running, asyncio.run can be used (but nest_asyncio should make this rare)
                return asyncio.run(
                    self.get_response_async(
                        query, callback, model, session_id, selected_text, mode, image_data)
                )
        except RuntimeError as e:
            if "cannot run nested event loops" in str(e) or "cannot schedule new futures after shutdown" in str(e):
                # This might happen if nest_asyncio isn't working as expected or due to shutdown sequences
                logging.error(
                    f"Caught common asyncio runtime error: {e}. Trying fallback loop management.")
                # Fallback: try creating a new loop specifically for this call (might have side effects)
                try:
                    return asyncio.run(
                        self.get_response_async(
                            query, callback, model, session_id, selected_text, mode, image_data)
                    )
                except Exception as fallback_e:
                    logging.error(
                        f"Fallback asyncio.run also failed: {fallback_e}")
                    raise fallback_e from e
            elif "attached to a different loop" in str(e):
                logging.error(
                    f"Caught asyncio loop error: {e}. This might indicate an issue with nest_asyncio or thread interaction.")
                raise e
            else:
                logging.error(f"Runtime error during sync wrapper: {e}")
                raise e
        except Exception as e:
            logging.exception(f"Error in get_response sync wrapper: {e}")
            raise

    def suggest_filename(self, content: str, session_id: str = "default") -> str:
        """Suggest a filename based on content and recent query history."""
        try:
            # Get message history for this session
            message_history = self.handler._get_message_history(session_id)

            # Get the most recent user query from history
            messages = message_history.messages
            recent_query = ""

            # Find the most recent user query
            if messages:
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        recent_query = msg.content
                        break

            # Update the filename suggester's detected language if we have one
            if self.detected_language:
                self.handler.filename_suggester.set_detected_language(
                    self.detected_language)
                # Reset our copy since the suggester will handle it
                self.detected_language = None

            # Get suggestion from the filename suggester
            return self.handler.filename_suggester.suggest_filename(content, recent_query)

        except Exception as e:
            logging.error(
                f"Error in suggest_filename: {str(e)}", exc_info=True)
            # Return default filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"dasi_response_{timestamp}.md"
