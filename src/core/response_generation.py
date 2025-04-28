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

            # Use LangChain's streaming capability directly
            accumulated_response = ""
            accumulated_chunk = None

            # We'll capture tool calls here if they happen
            detected_tool_calls = []

            # Process each chunk from the stream
            async for chunk in llm_instance.astream(state['messages']):
                # If this is our first chunk, remember it for accumulation
                if accumulated_chunk is None:
                    accumulated_chunk = chunk
                else:
                    # Otherwise, add this chunk to our accumulated chunk
                    accumulated_chunk = accumulated_chunk + chunk

                # Extract content for displaying in the UI
                chunk_content = chunk.content if hasattr(
                    chunk, 'content') else str(chunk)
                accumulated_response += chunk_content

                # Check for tool calls using LangChain's standardized interface
                if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                    # Log all tool call chunks we find
                    logging.info(
                        f"Tool call chunks in chunk: {chunk.tool_call_chunks}")
                    detected_tool_calls = chunk.tool_call_chunks

                # For compatibility, also check the tool_calls property
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    logging.info(f"Tool calls in chunk: {chunk.tool_calls}")
                    # This is the fully assembled tool call
                    detected_tool_calls = chunk.tool_calls

                # Pass the FULL accumulated response to the callback
                if callback:
                    try:
                        callback(accumulated_response)
                    except Exception as e:
                        logging.error(f"Error in callback: {e}")

            # Store the final accumulated response
            full_response = accumulated_response

            logging.info(
                f"Streaming completed. Final response length: {len(full_response)}")

            # Once streaming is done, check if we've accumulated any tool calls
            if accumulated_chunk and hasattr(accumulated_chunk, 'tool_calls') and accumulated_chunk.tool_calls:
                logging.info(
                    f"Final tool calls: {accumulated_chunk.tool_calls}")

                # Process each tool call from the standardized LangChain format
                for tool_call in accumulated_chunk.tool_calls:
                    # Extract the standard fields
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args')
                    tool_id = tool_call.get('id')

                    if tool_name and tool_args is not None:
                        logging.info(
                            f"Processing LangChain tool call: {tool_name} with ID: {tool_id}")

                        try:
                            # Request tool call confirmation from the user
                            self.handler.tool_call_handler.request_tool_call(
                                tool_name, tool_args)

                            # Use the tool call event from graph nodes
                            nodes.tool_call_event.clear()

                            # Log the start of waiting period
                            wait_start_time = time.monotonic()
                            logging.info(
                                f"Waiting for user to confirm tool call: {tool_name}")

                            # Update the UI callback if available to show we're waiting
                            if callback:
                                callback(
                                    accumulated_response + "\n\n[Waiting for your confirmation to use the tool...]")

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
                                            None, nodes.tool_call_event.wait, 1.0
                                        )
                                        if event_set:
                                            break  # Event was set

                                        # Check for timeout
                                        wait_duration = time.monotonic() - wait_start
                                        if wait_duration >= tool_call_timeout:
                                            logging.warning(
                                                f"Timeout waiting for tool call response for {tool_name}")
                                            # Set result to timeout error
                                            nodes.tool_call_result = {
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
                                        None, nodes.tool_call_event.wait, tool_call_timeout
                                    )
                                    if not event_set:
                                        logging.warning(
                                            f"Timeout waiting for tool call response for {tool_name}")
                                        # Set result to timeout error
                                        nodes.tool_call_result = {
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
                                nodes.tool_call_result = {
                                    'tool': tool_name,
                                    'id': tool_id,
                                    'result': {
                                        'status': 'error',
                                        'message': f'Error waiting for response: {str(e)}'
                                    }
                                }

                            # Clear the event for the next tool call
                            nodes.tool_call_event.clear()

                            # Get the result
                            result = nodes.tool_call_result

                            # Add the tool_call_id to the result for proper association
                            if result and isinstance(result, dict):
                                if 'id' not in result:
                                    result['id'] = tool_id

                            # If the result is not rejected
                            if result and result.get('result') != 'rejected':
                                # Create state with tool call result for a second round of processing
                                logging.info(
                                    "Processing tool results for follow-up response")

                                # Instead of reprocessing through prepare_messages, let's build a more focused
                                # conversation for the follow-up response
                                focused_messages = []

                                # Start with system message
                                focused_messages.append(
                                    SystemMessage(content=self.handler.system_prompt))

                                # Add a specific instruction for tool result analysis
                                analysis_instruction = f"""
This is the result of the {tool_name} tool call you requested.
Incorporate this information directly into your response to answer the user's question.
Be direct and informative in your response.
"""
                                focused_messages.append(
                                    SystemMessage(content=analysis_instruction))

                                # Add original user query as a human message
                                original_query = None
                                for msg in state['messages']:
                                    if isinstance(msg, HumanMessage):
                                        original_query = msg
                                        break

                                if original_query:
                                    focused_messages.append(HumanMessage(
                                        content=f"My original question was: {original_query.content}"))

                                # Convert tool result to a regular AI message instead of ToolMessage
                                if result and isinstance(result, dict):
                                    tool_content = None
                                    if isinstance(result.get('result'), dict) and 'data' in result['result']:
                                        tool_content = result['result']['data']
                                    elif isinstance(result.get('result'), str):
                                        tool_content = result['result']

                                    if tool_content:
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
                                                formatted_content = str(
                                                    tool_content)

                                            # Add a title to help the LLM understand what this tool result is
                                            final_tool_content = f"Tool result:\n\n{formatted_content}"

                                            # Use AIMessage instead of ToolMessage
                                            focused_messages.append(AIMessage(
                                                content=f"I retrieved this information for you:\n\n{final_tool_content}"))

                                        except Exception as e:
                                            logging.warning(
                                                f"Error formatting tool content: {e}")
                                            focused_messages.append(AIMessage(
                                                content=f"I retrieved this information for you: {str(tool_content)}"))

                                # Add a final prompt to analyze as human message
                                focused_messages.append(HumanMessage(
                                    content="Please analyze this information and provide a helpful response to my original question."))

                                # Use the focused messages instead of the full conversation
                                tool_state = state.copy()
                                tool_state['messages'] = focused_messages

                                # Log the messages being sent
                                logging.info(
                                    f"Prepared {len(focused_messages)} focused messages for follow-up LLM call")

                                # Log all messages for debugging
                                for i, msg in enumerate(focused_messages):
                                    content_preview = ""
                                    if hasattr(msg, 'content'):
                                        if isinstance(msg.content, str):
                                            content_preview = msg.content[:200] + (
                                                "..." if len(msg.content) > 200 else "")
                                        else:
                                            content_preview = str(msg.content)[
                                                :200] + ("..." if len(str(msg.content)) > 200 else "")
                                    logging.info(
                                        f"Focused message {i} ({type(msg).__name__}): {content_preview}")

                                # Get a second response from the LLM with the tool results
                                logging.info(
                                    "Getting follow-up response with tool results")

                                # Give the UI a moment to update with the tool result before continuing
                                await asyncio.sleep(0.5)

                                # Send initial empty chunk to signal continuation
                                if callback:
                                    callback(full_response + "\n\n")

                                # Explicitly check if the LLM instance is available
                                if not llm_instance:
                                    logging.error(
                                        "LLM instance not available for follow-up call")
                                    return full_response

                                # Log before the second LLM call
                                logging.info("Starting follow-up LLM stream")
                                start_time = time.monotonic()

                                # Stream the follow-up response separately from the original
                                follow_up_response = ""
                                follow_up_chunk = None

                                async for chunk in llm_instance.astream(tool_state['messages']):
                                    # Accumulate chunks for the follow-up response
                                    if follow_up_chunk is None:
                                        follow_up_chunk = chunk
                                    else:
                                        follow_up_chunk = follow_up_chunk + chunk

                                    # Extract content
                                    chunk_content = chunk.content if hasattr(
                                        chunk, 'content') else str(chunk)
                                    follow_up_response += chunk_content

                                    # Send the updated full text with each chunk
                                    if callback:
                                        try:
                                            # For the UI, we combine the original and follow-up
                                            combined_response = full_response + "\n\n" + follow_up_response
                                            callback(combined_response)
                                        except Exception as e:
                                            logging.error(
                                                f"Error in follow-up callback: {e}")

                                # Log after the second LLM call completes
                                end_time = time.monotonic()
                                duration = end_time - start_time
                                logging.info(
                                    f"Follow-up LLM stream completed in {duration:.3f} seconds")

                                # Check if the response is empty and log a warning
                                if not follow_up_response.strip():
                                    logging.warning(
                                        "Follow-up response is empty. The LLM didn't generate a proper analysis.")
                                    # Create a default follow-up response with a message about the issue
                                    follow_up_response = "The AI was unable to generate an analysis of the tool result. Please try asking your question again or in a different way."

                                # Log a preview of the follow-up response content
                                try:
                                    preview_length = min(
                                        200, len(follow_up_response))
                                    logging.info(
                                        f"Follow-up response content (first {preview_length} chars): {follow_up_response[:preview_length]}" +
                                        ("..." if len(follow_up_response)
                                         > preview_length else "")
                                    )
                                except Exception as e:
                                    logging.error(
                                        f"Error logging follow-up response: {e}")

                                # Update full response with the follow-up
                                # Combine original response with the follow-up response without visible separator
                                if follow_up_response.strip():
                                    # Use a simple newline break instead of the visible separator
                                    full_response = full_response.rstrip() + "\n\n" + follow_up_response
                                else:
                                    # If somehow still empty, don't modify the original response
                                    pass

                                # Ensure the UI displays this combined response first before signaling completion
                                if callback:
                                    callback(full_response)

                                # Signal that the tool call is complete and processing is done
                                # This helps ensure the UI is ready to show the response
                                try:
                                    # Short delay to ensure UI has updated with the final response
                                    QTimer.singleShot(
                                        100, lambda: self.handler.tool_call_handler.tool_call_processing.emit(tool_name))

                                    # Then after another delay, signal it's complete to transition UI
                                    QTimer.singleShot(300, lambda: self.handler.tool_call_handler.tool_call_completed.emit({
                                        "tool": tool_name,
                                        "id": tool_id,
                                        "result": "processed",  # Special flag to indicate UI should update
                                    }))
                                except Exception as e:
                                    logging.error(
                                        f"Error emitting tool_call_processing signal: {e}")

                                # Save the entire conversation to history
                                message_history = self.handler._get_message_history(
                                    session_id)
                                message_history.add_message(
                                    state['messages'][-1])  # User message

                                # Add tool message
                                tool_content = None
                                if isinstance(result.get('result'), dict) and 'data' in result.get('result'):
                                    tool_content = result.get(
                                        'result').get('data')
                                else:
                                    tool_content = str(result.get('result', {}).get(
                                        'data', 'Tool execution completed'))

                                message_history.add_message(AIMessage(
                                    content=f"I retrieved this information: {tool_content}"))

                                # Add final AI response
                                message_history.add_message(
                                    AIMessage(content=full_response))
                                return full_response
                            else:
                                # Just save the normal conversation if tool was rejected
                                message_history = self.handler._get_message_history(
                                    session_id)
                                message_history.add_message(
                                    state['messages'][-1])
                                message_history.add_message(
                                    AIMessage(content=full_response))

                            # Reset the tool_call_result to avoid reuse
                            nodes.tool_call_result = None

                        except Exception as e:
                            logging.error(
                                f"Error processing tool call: {e}", exc_info=True)
                            # Save normal conversation on error
                            message_history = self.handler._get_message_history(
                                session_id)
                            message_history.add_message(state['messages'][-1])
                            message_history.add_message(
                                AIMessage(content=full_response))

            # Store in chat history for normal responses (if we didn't already save it during tool call handling)
            message_history = self.handler._get_message_history(session_id)
            message_history.add_message(
                state['messages'][-1])  # Add the user message
            message_history.add_message(
                AIMessage(content=full_response))  # Add the AI response

            # Handle post-processing for compose mode
            if state['mode'] == 'compose':
                processed_response, detected_language = self._extract_code_block(
                    full_response)
                self.detected_language = detected_language
                return processed_response

            return full_response

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
