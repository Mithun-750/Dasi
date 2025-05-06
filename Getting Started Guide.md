# Dasi Getting Started Guide

This guide provides essential information for getting started with Dasi, the desktop copilot application.

## Table of Contents
- [Dasi Getting Started Guide](#dasi-getting-started-guide)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
    - [First Launch](#first-launch)
    - [System Tray](#system-tray)
  - [Basic Usage](#basic-usage)
    - [Quick Start](#quick-start)
    - [Selecting Text](#selecting-text)
    - [Keyboard Shortcuts](#keyboard-shortcuts)
  - [Operation Modes](#operation-modes)
    - [💬 Chat Mode](#-chat-mode)
    - [✍️ Compose Mode](#️-compose-mode)
  - [Prompt Chunks](#prompt-chunks)
    - [Creating Prompt Chunks](#creating-prompt-chunks)
    - [Using Prompt Chunks](#using-prompt-chunks)
  - [Advanced Features](#advanced-features)
    - [Tool Calling](#tool-calling)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Getting Help](#getting-help)

## Getting Started

### First Launch
When you first run Dasi, if no models are set, the settings window will automatically appear:

1. Go to the "API Keys" tab and enter your API keys
   - **Fun Fact**: You can use the API key from Google AI Studio to access state-of-the-art models like Gemini 2.5 Flash for free
   - If you don't see a provider listed, you can still add it as a custom OpenAI-compatible endpoint

2. Navigate to the "Models" tab 
   - Here you'll find all the models from providers you've added API keys for
   - This list is dynamic as it's fetched through the respective /models endpoint

3. Start Dasi using the button in the bottom left corner of the settings window

4. Close the settings window - Dasi will continue running in the background
   - You'll see a Dasi icon in your system tray
   - Through this icon, you can open settings or stop Dasi

5. Trigger Dasi with the hotkey `Ctrl+Alt+Shift+I` (customizable through settings)
   - A popup will appear near your cursor
   - Here you can send queries to your selected LLMs

### System Tray
The system tray icon provides quick access to:
- Open Settings
- Stop Dasi
- Trigger Dasi (popup will appear in the center of your screen)

## Basic Usage

### Quick Start
1. Press `Ctrl+Alt+Shift+I` to summon Dasi
2. Type your query in the input box
3. Press Enter to submit
4. View the AI's response in the chat window
5. Continue the conversation or close the window

### Selecting Text
For context-aware assistance:
1. Select text in any application
2. Press the global hotkey
3. Dasi will use the selected text as context for your query

### Keyboard Shortcuts
- **Enter**: Submit your query
- **Esc**: Close Dasi
- **Shift+Enter**: Insert a line break in your query

## Operation Modes

Dasi offers two primary modes of operation:

### 💬 Chat Mode
- Interactive conversation with the AI
- Multi-turn dialogue support
- History is preserved during the session
- Best for: explanations, brainstorming, Q&A

To use Chat Mode:
1. Ensure "Chat" is selected in the mode toggle
2. Enter your question or prompt
3. Continue the conversation as needed

### ✍️ Compose Mode
- Direct content generation
- Output can be copied or typed into the active application
- Best for: writing emails, creating content, code generation

To use Compose Mode:
1. Switch to "Compose" in the mode toggle
2. Enter your generation request (e.g., "Write an email to schedule a meeting")
3. After receiving the response, you'll see two additional options:
   - **Use**: Automatically pastes the response where your cursor was last positioned
   - **Export**: Saves the response to a file
4. Look for the pencil icon in the bottom right corner - this allows you to edit the response before using or exporting it

## Prompt Chunks

Prompt Chunks are reusable templates that can be referenced in your queries using @mentions.

### Creating Prompt Chunks
1. Access Settings via the system tray icon
2. Navigate to the "Prompt Chunks" tab
3. Click "Create New Chunk"
4. Enter a title (without spaces) and content
5. Click "Save"

### Using Prompt Chunks
Simply include the chunk name with an @ symbol in your query:
- "Write a professional email @email_template"
- "Explain this code @code_explainer"

## Advanced Features

### Tool Calling
Dasi supports various system tools that extend the AI's capabilities:

- **Web Search**: Search the internet for up-to-date information
- **System Info**: Access information about your system
- **Terminal Commands**: Execute commands in your terminal

Enable or disable these in Settings → Tools.

## Troubleshooting

### Common Issues

**Dasi doesn't appear when using the hotkey**
- Check if Dasi is running in the system tray
- Try restarting the application
- Verify the hotkey isn't conflicting with another application

**API errors**
- Verify your API keys are correct
- Check your internet connection
- Ensure the selected model provider is operational

**Text insertion not working**
- Make sure your active window accepts text input
- Try using Copy to Clipboard instead
- Check if your system's accessibility settings allow simulated typing

### Getting Help
If you encounter issues not covered in this guide:
- Check the [GitHub Issues](https://github.com/Mithun-750/Dasi/issues) for known problems
- Submit a new issue with detailed reproduction steps 