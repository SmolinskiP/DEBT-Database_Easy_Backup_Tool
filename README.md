# DB Backup Tool

A web-based backup tool for MySQL/MariaDB databases. Supports both direct TCP/IP connections and SSH tunneling.

## Features

- Database server management
- Connection testing
- Database backup creation
- Backup scheduling
- Operation history

## Requirements

- Python 3.8+
- Django 5.2+
- MySQL/MariaDB client
- Access to database servers

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/db-backup-tool.git
   cd db-backup-tool
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

3. Create .env file from .env.example and customize:
   ```
   cp .env.example .env
   # Edit .env with appropriate values
   ```

4. Run database migrations:
   ```
   python manage.py migrate
   ```

5. Start the development server:
   ```
   python manage.py runserver
   ```

6. Go to http://127.0.0.1:8000 in your browser

## Configuration

All sensitive settings are stored in the `.env` file. Make sure this file is not placed in a public repository.

## License

[MIT License](LICENSE)