# PostgreSQL Setup Guide

This bot now uses PostgreSQL exclusively. No SQLite support.

## Required Environment Variables

```bash
POSTGRES_HOST=your_postgres_host
POSTGRES_PORT=5432
POSTGRES_DB=shop_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### Alternative - Use Full URL:
```bash
DATABASE_URL=postgresql://username:password@host:port/database
```

## Render.com Setup

1. **Add PostgreSQL Service:**
   - Go to your Render dashboard
   - Click "New +" → "PostgreSQL"
   - Choose your plan and region
   - Note the connection details

2. **Update Environment Variables:**
   - Go to your bot service settings
   - Add these environment variables:
     ```
     POSTGRES_HOST=<from your PostgreSQL service>
     POSTGRES_PORT=5432
     POSTGRES_DB=<from your PostgreSQL service>
     POSTGRES_USER=<from your PostgreSQL service>
     POSTGRES_PASSWORD=<from your PostgreSQL service>
     ```

3. **Deploy:**
   - The bot will automatically create all necessary tables on first run
   - No manual database setup required

## Local Development

1. **Install PostgreSQL:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   
   # macOS
   brew install postgresql
   
   # Windows
   # Download from https://www.postgresql.org/download/windows/
   ```

2. **Create Database:**
   ```bash
   sudo -u postgres createdb shop_db
   ```

3. **Set Environment Variables:**
   ```bash
   export POSTGRES_HOST=localhost
   export POSTGRES_PORT=5432
   export POSTGRES_DB=shop_db
   export POSTGRES_USER=postgres
   export POSTGRES_PASSWORD=your_password
   ```

## Migration from SQLite

If you have existing SQLite data, you'll need to export it and import it into PostgreSQL manually. The bot will automatically create all necessary tables on first run.

## Benefits of PostgreSQL

- **Better Performance:** Handles concurrent connections better
- **Scalability:** Can handle larger datasets
- **Advanced Features:** JSON support, full-text search, etc.
- **Production Ready:** Better for production deployments
- **ACID Compliance:** Better data integrity guarantees

## PostgreSQL Only

This bot now requires PostgreSQL. SQLite support has been completely removed for better performance and scalability.
