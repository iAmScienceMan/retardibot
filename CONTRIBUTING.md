# Contributing Guidelines for retardibot

## Introduction

Thank you for your interest in contributing to retardibot, the utility and AI-powered chatbot for the femboy retardia Discord server. This document outlines the guidelines for contributing to the project, ensuring consistency and quality across all contributions.

## Code of Conduct

Despite the casual nature of our community, we expect all contributors to:
- Maintain respectful communication
- Provide constructive feedback
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully

## Getting Started

### Setting Up Your Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/iAmScienceMan/retardibot.git
   cd retardibot
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your environment**
   - Rename `.env.example` to `.env`
   - Fill in necessary credentials (Discord token, OpenAI API key, etc.)

5. **Run the bot locally**
   ```bash
   python bot.py
   ```

## Development Guidelines

### Code Style

- Follow PEP 8 standards for Python code
- Use meaningful variable and function names
- Include docstrings for classes and functions
- Add comments for complex logic

### Bot Architecture

- Utilize the `disnake` library for Discord interactions
- Organize code using cogs for modularity
- Implement command-based configuration
- Use only slash commands, with limited exceptions for utility commands that require quick access

### Git Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit your changes with clear commit messages**
4. **Push your branch to your fork**
5. **Submit a pull request to the main repository**

## Contribution Types

### Bug Reports

When submitting a bug report, please include:
- A clear description of the issue
- Steps to reproduce the problem
- Expected vs. actual behavior
- Screenshots or error logs if applicable
- Environment information (OS, Python version, etc.)

### Feature Requests

Before submitting a feature request:
- Check the issue tracker to avoid duplicates
- Discuss your idea in the Discord server
- Provide a clear use case for the feature

When submitting:
- Describe the feature in detail
- Explain how it benefits the bot/community
- Include any design considerations

### Code Contributions

Before starting work on major contributions:
- Open an issue to discuss the proposed changes
- Wait for feedback from maintainers
- Plan your implementation approach

For all code contributions:
- Write and include tests when applicable
- Update documentation as needed
- Follow the code style guidelines
- Ensure your code passes all existing tests

## Pull Request Process

1. Ensure your code adheres to the project's style guidelines
2. Update the README.md or documentation with any necessary changes
3. Add your changes to the CHANGELOG.md *(when I finally add one)*
4. The pull request will be reviewed by maintainers
5. Address any requested changes promptly
6. Once approved, a maintainer will merge your contribution

## Documentation

- Update documentation for any changes to the user interface or commands
- Document new features thoroughly
- Keep the README.md updated with any significant changes
- Use clear and concise language

## Community Involvement

- Join discussions in the Discord server
- Help answer questions from other contributors
- Provide feedback on open issues and pull requests
- Participate in feature planning and roadmap discussions

## Contact

If you have questions or need assistance, please reach out:
- Discord server: https://discord.gg/bM5dKU8Qk9
- GitHub issues: https://github.com/iAmScienceMan/retardibot/issues

Thank you for contributing to retardibot! Your efforts help improve the experience for our entire community.
