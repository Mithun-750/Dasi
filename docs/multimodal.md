# Multimodal Capabilities in Dasi

This document explains how to use and configure Dasi's multimodal capabilities, which allow the application to handle both text and images in conversations with AI models.

## Overview

Dasi supports multimodal inputs (text + images) with compatible AI models from providers such as OpenAI, Google, and Anthropic. This allows you to:

- Paste images directly into the chat interface
- Drag and drop images into the conversation
- Include both images and text in your queries
- Get AI responses analyzing or referring to the visual content

## Supported Models

The following models are known to support multimodal inputs:

| Provider      | Compatible Models                          |
| ------------- | ------------------------------------------ |
| OpenAI        | GPT-4o, GPT-4 Vision, GPT-4 Turbo          |
| Google        | Gemini models (Pro Vision, Advanced, etc.) |
| Anthropic     | Claude 3 models (Opus, Sonnet, Haiku)      |
| Custom OpenAI | Any compatible models on custom endpoints  |

## Configuration

### Setting up a Vision Model

1. Navigate to **Settings → Models**
2. In the **Vision Model** section, select a model capable of processing images
3. If no model is selected, Dasi will attempt to use the most compatible model when an image is present, but explicit selection is recommended

### Vision Model Detection

Dasi uses several methods to identify vision-capable models:
- Model ID matching for known models (e.g., GPT-4o, Gemini, Claude 3)
- Keywords in model names such as "vision", "multimodal", or "visual"
- Provider-specific model capabilities

## Using Multimodal Features

### Inserting Images

You can add images to your conversations in two ways:

1. **Clipboard Paste**: Copy an image to your clipboard and press `Ctrl+V` in the input area
2. **Drag and Drop**: Drag an image file from your file explorer and drop it into Dasi's input field

Once an image is inserted:
- A preview will appear above the text input
- The image will be automatically resized for display
- A warning will show if no vision model is selected

### Image Processing

When an image is added to the conversation:

1. The image is converted to base64 format for API compatibility
2. The system checks for a configured vision model
3. If a vision model is selected, it will be used for the conversation
4. If no vision model is selected, Dasi will try to find a compatible model from the current provider
5. If no compatible model is found, a warning will be shown in the response

### Context Handling

Dasi supports combining different types of context in a single query:

- **Selected Text**: Text you've selected elsewhere on your screen before activating Dasi
- **Images**: Visual content added to the conversation
- **Query Text**: Your typed question or prompt

These context elements are formatted appropriately based on the LLM provider's requirements.

## Technical Implementation

### Code Organization

The multimodal functionality is distributed across several files in the Dasi codebase:

- `src/llm_handler.py`: Core logic for handling multimodal requests
- `src/ui/popup/components/input_panel.py`: UI components for image input and display
- `src/ui/popup/window.py`: Integration between UI and backend
- `src/ui/settings/models_tab.py`: Vision model configuration interface

### LLM Handler

The `LLMHandler` class (in `src/llm_handler.py`) is responsible for managing LLM interactions:

#### Vision Model Initialization

```python
def initialize_llm(self, model_name: str = None) -> bool:
    # ...
    # Special case for vision models: allow partial matching
    if model_name == vision_model_id:
        logging.info(f"Using vision model: {model_name}")
        # Find the model by exact ID match or by partial match
        model_info = next((m for m in selected_models if m['id'] == model_name), None)
        if not model_info:
            # Try to match by base name for vision models
            base_name = model_name.split('/')[-1] if '/' in model_name else model_name
            logging.info(f"Trying to match vision model with base name: {base_name}")
            for m in selected_models:
                model_id = m['id']
                if base_name in model_id or model_id in model_name:
                    model_info = m
                    logging.info(f"Found vision model by partial match: {m['id']}")
                    break
    # ...
```

This enables flexible matching of vision models, which is critical as model IDs often include version or provider-specific prefixes.

#### Provider-Specific Initialization

Each provider requires different initialization for vision capabilities:

```python
# For Google's Gemini models
self.llm = ChatGoogleGenerativeAI(
    model=model_id,  # Keep the full model ID including 'models/' prefix
    google_api_key=self.settings.get_api_key('google'),
    temperature=temperature,
)

# For OpenAI's GPT-4o and vision models
if 'gpt-4o' in model_id.lower() or 'vision' in model_id.lower():
    self.llm = ChatOpenAI(
        model=model_id,
        temperature=temperature,
        streaming=True,
        openai_api_key=self.settings.get_api_key('openai'),
        max_tokens=4096,  # Set a reasonable limit for vision models
    )
    
# For Anthropic's Claude 3 models
if 'claude-3' in model_id.lower():
    self.llm = ChatAnthropic(
        model=model_id,
        anthropic_api_key=self.settings.get_api_key('anthropic'),
        temperature=temperature,
        streaming=True,
        max_tokens=4096,  # Set a reasonable limit for vision requests
    )
```

#### Multimodal Message Construction

The `get_response` method creates content blocks for multimodal requests:

```python
# Create multimodal message content
if image_data:
    # Format selected text if available
    if 'selected_text' in context:
        final_query = f"{actual_query}\n\nText context: {context['selected_text']}"
    else:
        final_query = actual_query

    # Create multimodal message content using content blocks
    content_blocks = [
        {"type": "text", "text": final_query},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_data}"}
        }
    ]

    # Create human message with multimodal content
    query_message = HumanMessage(content=content_blocks)
```

This format is compatible with LangChain's multimodal message structure, which works with all supported providers.

### Input Panel Implementation

The `InputPanel` class implements image handling at the UI level:

#### Custom PlainTextEdit for Image Support

```python
# Custom QTextEdit that pastes plain text only and accepts image drops
class PlainTextEdit(QTextEdit):
    """A QTextEdit that ignores formatting when pasting text and supports image drops."""

    image_pasted = pyqtSignal(QImage)
    image_dropped = pyqtSignal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        """Override to insert plain text only."""
        if source.hasImage():
            image = QImage(source.imageData())
            self.image_pasted.emit(image)
        elif source.hasText():
            self.insertPlainText(source.text())
```

#### Image Processing Method

The core image processing happens in the `_process_image` method:

```python
def _process_image(self, image: QImage):
    """Process and display an image."""
    if image.isNull():
        logging.error("Received null image")
        return
        
    # Store the image
    self.image = image
    
    # Convert image to base64
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    image.save(buffer, "PNG")
    image_data = buffer.data().data()
    self.image_data = base64.b64encode(image_data).decode('utf-8')
    
    # Resize image for display (maintaining aspect ratio)
    scaled_image = image.scaled(300, 150, Qt.AspectRatioMode.KeepAspectRatio, 
                               Qt.TransformationMode.SmoothTransformation)
    
    # Display image
    self.image_label.setPixmap(QPixmap.fromImage(scaled_image))
    self.image_label.show()
    
    # Show context frame and ignore button
    self.context_frame.show()
    self.ignore_button.show()
    
    # Show a message if the vision model isn't set
    vision_model = self.settings.get('models', 'vision_model')
    if not vision_model:
        self.context_label.setText("Warning: No vision model selected in settings! Image will be ignored.")
        self.context_label.show()
```

This method handles:
1. Base64 conversion for API compatibility
2. Image resizing for preview display
3. UI updates to show the image
4. Warning display if no vision model is set

### Window Implementation

The `DasiWindow` class in `window.py` manages the context between UI and backend:

```python
def _handle_input_submit(self, text: str):
    # ...
    # Build context dictionary with selected text and mode
    context = {}
    if self.selected_text:
        context['selected_text'] = self.selected_text
    if hasattr(self.input_panel, 'image_data') and self.input_panel.image_data:
        context['image_data'] = self.input_panel.image_data
        
    # Format full query with context
    full_query = f"Context:\n"
    
    if self.selected_text:
        full_query += f"=====SELECTED_TEXT=====<text selected by the user>\n{self.selected_text}\n=======================\n\n"
        
    if 'image_data' in context:
        full_query += f"=====IMAGE_DATA=====\n{context['image_data']}\n=======================\n\n"
        
    # Include mode in context
    full_query += f"=====MODE=====<user selection>\n{mode}\n=======================\n\n"
    full_query += f"Query:\n{text}"
    # ...
```

This code formats the full query with properly delimited sections for:
- Selected text
- Image data (in base64 format)
- Mode information (chat or compose)

### Models Tab Implementation

The `ModelsTab` class handles UI for vision model selection:

```python
def _is_vision_capable(self, model):
    """Check if a model is likely to support vision capabilities."""
    provider = model['provider']
    model_id = model['id'].lower()
    model_name = model['name'].lower()

    # Models known to support vision
    if provider == 'openai' and ('gpt-4-vision' in model_id or 'gpt-4o' in model_id or 'gpt-4-turbo' in model_id):
        return True
    elif provider == 'google' and ('gemini' in model_id):
        return True
    elif provider == 'anthropic' and ('claude-3' in model_id):
        return True
    elif provider == 'custom_openai' and ('gpt-4-vision' in model_id or 'gpt-4o' in model_id):
        return True

    # Check for known model names
    vision_keywords = ['vision', 'multimodal', 'image',
                       'visual', 'gpt-4o', 'gemini', 'claude-3']
    for keyword in vision_keywords:
        if keyword in model_id or keyword in model_name:
            return True

    return False
```

This method identifies models that are likely to support vision capabilities, which is used to populate the vision model selection dropdown.

### Fallback Mechanisms

Dasi includes several fallback strategies to handle cases where the configured vision model isn't available:

1. **Partial Name Matching**: Matches against model name without provider prefixes
2. **Provider-Based Inference**: Looks for compatible models from the same provider
3. **Keyword Detection**: Identifies vision models by common terms in names

```python
# Find compatible vision models from the same provider
for m in selected_models:
    if m['provider'] == provider:
        model_id = m['id'].lower()
        model_name = m['name'].lower()
        
        # Check for vision capabilities by provider and model ID
        if ((provider == 'openai' and ('gpt-4-vision' in model_id or 'gpt-4o' in model_id)) or
            (provider == 'google' and 'gemini' in model_id) or 
            (provider == 'anthropic' and 'claude-3' in model_id) or
            any(keyword in model_id or keyword in model_name 
                for keyword in ['vision', 'multimodal', 'visual'])):
            compatible_model = m
            break
```

## Troubleshooting

### Image Not Being Processed

If your image isn't being processed correctly:

1. **Check Vision Model**: Ensure you have a compatible vision model selected in Settings
2. **API Keys**: Verify you have valid API keys for the selected model's provider
3. **Image Format**: Ensure the image is in a standard format (PNG, JPG, etc.)
4. **Image Size**: Very large images may cause issues; try resizing before adding them

### Model Compatibility

If you receive an error about vision capabilities:

1. **Provider Support**: Confirm your chosen provider supports multimodal inputs
2. **Model Selection**: Select a vision-capable model explicitly in Settings
3. **Check Log**: Application logs may provide more details about model compatibility issues

## Examples

### Analyzing an Image

1. Paste or drop an image into the input field
2. Ask a question like: "What can you see in this image?" or "Describe what's in this picture."
3. Submit your query

### Contextual Questions

For more specific analysis:

1. Add an image to the conversation
2. Ask targeted questions like:
   - "What text appears in this image?"
   - "Are there any issues with this design?"
   - "Explain the code in this screenshot."

## Future Enhancements

Planned improvements for multimodal functionality:

- Support for multiple images in a single conversation
- Image editing capabilities within the app
- Better handling of large or high-resolution images
- Additional multimodal providers as they become available 