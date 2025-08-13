# FastApp project

A FastApp project - Python framework for rapid application development.

## Quick Start

1. **Install dev dependencies:**
   ```bash
   pip install "fast-app[dev]"
   ```

2. **Set up environment:**
   ```bash
   cp env.debug.example .env.debug
   # Edit .env with your configuration
   ```

3. **Run the application:**
   ```bash
   fast-app run api
   ```

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

For more information about FastApp, visit: https://github.com/patrikmojzis/fast-app