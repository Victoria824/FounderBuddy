# Deployment Configuration

## Files in this directory

- **Procfile**: Heroku deployment configuration
- **runtime.txt**: Python runtime version specification

## Deployment

### Heroku
Use `Procfile` and `runtime.txt`:
```bash
git push heroku main
```

## Configuration Notes
- Port 8080 is configured for Heroku
- Health check endpoint: `/info`