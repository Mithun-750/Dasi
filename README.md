# Linux Copilot

A simple Linux copilot tool that provides AI assistance through a global hotkey popup interface.

## Features

- Global hotkey (Ctrl+Alt+Shift+I) to activate
- Popup input window at cursor position
- AI-powered responses using Google's Gemini model
- Automatic response typing at cursor position

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```
   Get your API key from: https://ai.google.dev/gemini-api/docs/api-key

3. Run the application:
   ```bash
   python src/main.py
   ```

## Usage

1. Press Ctrl+Alt+Shift+I anywhere to bring up the input window
2. Type your query and press Enter
3. The AI response will be typed at your current cursor position

## Requirements

- Pop!_OS 22.04 LTS or compatible Linux distribution
- Python 3.8+
- X11 display server
