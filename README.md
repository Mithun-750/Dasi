# <img src="src/assets/Dasi.png" alt="Dasi Logo" width="32" style="vertical-align: middle"> Dasi

<div align="center">
A powerful desktop copilot that provides inline LLM support using LangChain and multiple AI model providers.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyQt](https://img.shields.io/badge/PyQt-6.0+-blue.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![LangChain](https://img.shields.io/badge/LangChain-Latest-orange.svg)](https://python.langchain.com/)
[![uv](https://img.shields.io/badge/uv-Latest-blueviolet.svg)](https://astral.sh/uv)

[🌟 Features](#-features) • [🚀 Installation](#-installation) • [💡 Usage](#-usage) • [⚙️ Configuration](#%EF%B8%8F-configuration) • [🤝 Contributing](#-contributing)

<img src="images/image.png" alt="Dasi">
</div>

## 🌟 Features

### Core Functionality
- **Global Hotkey**: Instant activation with Ctrl+Alt+Shift+I (customizable)
- **Smart Popup**: Modern, borderless interface that appears near your cursor
- **Context-Aware**: Utilizes selected text for enhanced responses
- **Dual Operation Modes**:
  - 💬 **Chat Mode**: Interactive conversations and explanations
  - ✍️ **Compose Mode**: Direct content generation and insertion

### AI Integration
- **Multiple Model Providers**:
  - 🧠 Google Gemini
  - 🤖 OpenAI
  - 🔮 Anthropic
  - ⚡ Groq
  - 🏠 Ollama (local models)
  - 🌊 Deepseek
  - 🤝 Together AI
  - 🌐 OpenRouter
  - 🛠️ Custom OpenAI-compatible endpoints

### Advanced Features
- **Prompt Chunks**: Template system with @mention support
- **Flexible Output**: Choose between copy/paste or simulated typing
- **Rich Settings**:
  - API configuration
  - Model selection and defaults
  - Custom instructions
  - Temperature control
  - Startup behavior

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- uv package manager (follow [installation guide](https://astral.sh/uv))
- For Windows users: `pywin32` and `winshell` packages (optional, for shortcut creation)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Mithun-750/Dasi.git
   cd Dasi
   ```

2. Run the installation script:
   ```bash
   python installer.py install
   ```

   This will:
   - Set up a virtual environment (or use an existing one)
   - Install all dependencies
   - Build the application using PyInstaller
   - Create a desktop shortcut/launcher (desktop entry on Linux, shortcut on Windows, or symlink on macOS)

3. Launch Dasi:
   - **Linux:** From your applications menu or run `dist/dasi/dasi`
   - **macOS:** From the Applications folder or run `dist/dasi/dasi`
   - **Windows:** From the Start Menu or run `dist\dasi\dasi.exe`

### Development Setup

If you want to run Dasi locally for development:

1. Clone the repository:
   ```bash
   git clone https://github.com/Mithun-750/Dasi.git
   cd Dasi
   ```

2. Install uv (if not already installed) and set up the project:
   ```bash
   # Install uv if needed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install project in development mode with all dependencies
   uv pip install -e .
   ```

3. Use Invoke commands to manage your development workflow:
   ```bash
   # Run the application in development mode
   inv dev
   
   # Update dependencies after changing pyproject.toml
   inv install  # This runs 'uv pip install -e .'
   
   # Sync dependencies with the lockfile
   inv sync
   
   # Build the application
   inv build
   ```

This setup is recommended for:
- Development and testing
- Making contributions
- Debugging issues
- Testing new features

### Uninstallation

To uninstall Dasi, run:
```bash
python installer.py uninstall
```

This will remove:
- Application shortcuts (desktop entry/shortcut/symlink)
- Configuration files
- Build artifacts  
*Note:* The source code and virtual environment remain intact.

## 💡 Usage

### Quick Start
1. Press `Ctrl+Alt+Shift+I` to summon Dasi
2. Type your query or use @mentions for prompt chunks
3. Press Enter to submit

### Compose Mode
1. Switch to Compose mode using the toggle
2. Enter your generation request
3. Choose output method (Copy/Paste or Type Text)
4. Click Accept to insert or Reject to dismiss

### Prompt Chunks
Create reusable templates:
1. Open Settings → Prompt Chunks
2. Click "Create New Chunk"
3. Enter title and content
4. Reference in queries with @mention (e.g., "@email_template")

## ⚙️ Configuration

### API Setup
1. Launch Dasi and access Settings via system tray
2. Navigate to "API Keys" tab
3. Add your API keys for desired providers
4. Select and configure models in "Models" tab

### Customization
- **Custom Instructions**: Add global context for all queries
- **Temperature**: Adjust response creativity
- **Startup**: Configure autostart and initial behavior
- **Hotkeys**: Customize activation shortcuts

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Install project dependencies:
   ```bash
   uv pip install -e .
   ```
4. Make your changes
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://python.langchain.com/) for the AI integration framework
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework
- [Cursor IDE](https://cursor.sh/) for the incredible development environment that helped build this project
- All the AI model providers for their APIs

