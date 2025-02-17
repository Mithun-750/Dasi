# Dasi

A powerful desktop copilot that provides inline LLM support using LangChain and multiple AI model providers.

## Features

- **Global Hotkey**: Activate with Ctrl+Alt+Shift+I (customizable in settings)
- **Smart Popup**: Modern, borderless input window that appears near your cursor
- **Multiple AI Models Support**:
  - Google Gemini
  - OpenAI
  - Anthropic
  - Groq
  - Ollama (local models)
  - Deepseek
  - Together AI
  - OpenRouter
  - Custom OpenAI-compatible endpoints
- **Dual Operation Modes**:
  - Chat Mode: For conversational interactions and explanations
  - Compose Mode: For generating content to be inserted
- **Prompt Chunks**: Create and reuse prompt templates with @mentions
- **Context-Aware**: Can use selected text as context for queries
- **Flexible Output**: Choose between copy/paste or simulated typing for responses
- **Customizable Settings**:
  - API configurations
  - Model selection and defaults
  - Custom instructions
  - Temperature control
  - Startup behavior

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API Keys:
   - Launch Dasi and open Settings (from system tray icon)
   - Go to "API Keys" tab
   - Add your API key(s) for desired providers
   - Select models in the "Models" tab

3. Run the application:
   ```bash
   python src/main.py
   ```

## Usage

1. Press Ctrl+Alt+Shift+I (or your configured hotkey) anywhere to open Dasi
2. Type @ to access saved prompt chunks
3. Enter your query and press Enter
4. For Compose Mode:
   - Select output method (Copy/Paste or Type Text)
   - Click Accept to insert the response
   - Click Reject to dismiss

## Prompt Chunks

Create reusable prompt templates:
1. Open Settings → Prompt Chunks
2. Click "Create New Chunk"
3. Enter title and content
4. Use with @mention in queries (e.g., "@test_chat")

## Developed and tested on

- Pop!\_OS 22.04 LTS (GNOME desktop)
- Python 3.8+
- X11 display server
- Required libraries (see requirements.txt)

## Development Status

This is an actively developed project. For bugs or feature requests, please open an issue on GitHub.
