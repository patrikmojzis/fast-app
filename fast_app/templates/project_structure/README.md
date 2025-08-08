# FastApp project

A FastApp project - Laravel-inspired Python framework for rapid application development.

## Features

- **FastAPI Integration** - Modern, fast web framework
- **MongoDB Support** - Async MongoDB operations
- **Redis Caching** - Built-in caching layer
- **Observer Pattern** - Event-driven architecture
- **Policy-based Authorization** - Flexible access control
- **Notification System** - Multi-channel notifications
- **Structured Architecture** - Clean, organized codebase

## Project Structure

```
{project_name}/
├── app/
│   ├── http_files/
│   │   ├── controllers/     # HTTP request handlers
│   │   ├── resources/       # API resource transformers
│   │   ├── schemas/         # Pydantic models
│   │   ├── services/        # Business logic
│   │   └── routes/          # Route definitions
│   ├── models/              # Data models
│   ├── observers/           # Event observers
│   ├── notifications/       # Notification system
│   └── policies/            # Authorization policies
├── docker/                  # Docker configuration
├── main.py                  # Application entry point
└── requirements.txt         # Dependencies
```

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp env.debug.example .env.debug
   # Edit .env with your configuration
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

4. **Access the API:**
   - API: http://localhost:8000/api/v1/
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/api/v1/health

## Development

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\\Scripts\\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

Ensure MongoDB is running locally or update the connection string in your `.env` file.

### Redis Setup

Ensure Redis is running locally or update the connection string in your `.env` file.

## Docker Support

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Testing

```bash
pytest
```

## Built with FastApp

This project was generated using the FastApp CLI:

```bash
fast-app init
```

For more information about FastApp, visit: https://github.com/patrikmojzis/fast-app