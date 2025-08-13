#!/usr/bin/env python3
"""
Automated database migration system for Render deployment
Runs migrations safely on each deployment using DATABASE_URL
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationRunner:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        
        # Get environment to determine schema
        self.environment = os.getenv('ENVIRONMENT', 'production')
        self.schema = 'preview' if self.environment == 'preview' else 'public'
        
        logger.info(f"🌍 Environment: {self.environment}")
        logger.info(f"📊 Target schema: {self.schema}")
        
        # Find migrations directory
        self.migrations_dir = Path(__file__).parent / 'migrations'
        if not self.migrations_dir.exists():
            raise FileNotFoundError(f"Migrations directory not found: {self.migrations_dir}")
    
    def check_psql_available(self) -> bool:
        """Check if psql command is available"""
        try:
            subprocess.run(['psql', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def create_migration_tracking_table(self) -> bool:
        """Create table to track which migrations have been applied"""
        sql = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};
        CREATE TABLE IF NOT EXISTS {self.schema}.migration_history (
            id SERIAL PRIMARY KEY,
            migration_name VARCHAR(255) UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT NOW(),
            success BOOLEAN DEFAULT TRUE,
            environment VARCHAR(50) DEFAULT '{self.environment}'
        );
        """
        
        try:
            result = subprocess.run([
                'psql', self.database_url, '-c', sql
            ], capture_output=True, text=True, check=True)
            logger.info(f"✅ Migration tracking table ready in {self.schema} schema")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to create migration tracking table: {e.stderr}")
            return False
    
    def is_migration_applied(self, migration_name: str) -> bool:
        """Check if a migration has already been applied"""
        sql = f"SELECT COUNT(*) FROM {self.schema}.migration_history WHERE migration_name = '{migration_name}' AND success = TRUE;"
        
        try:
            result = subprocess.run([
                'psql', self.database_url, '-t', '-c', sql
            ], capture_output=True, text=True, check=True)
            
            count = int(result.stdout.strip())
            return count > 0
        except (subprocess.CalledProcessError, ValueError):
            return False
    
    def mark_migration_applied(self, migration_name: str, success: bool = True) -> None:
        """Mark a migration as applied in the tracking table"""
        sql = f"""
        INSERT INTO {self.schema}.migration_history (migration_name, success, environment) 
        VALUES ('{migration_name}', {success}, '{self.environment}') 
        ON CONFLICT (migration_name) 
        DO UPDATE SET applied_at = NOW(), success = {success}, environment = '{self.environment}';
        """
        
        try:
            subprocess.run([
                'psql', self.database_url, '-c', sql
            ], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to mark migration {migration_name}: {e.stderr}")
    
    def run_migration_file(self, file_path: Path, description: str) -> bool:
        """Run a single migration file"""
        migration_name = file_path.name
        
        # Check if already applied
        if self.is_migration_applied(migration_name):
            logger.info(f"⏭️  Skipping {migration_name} (already applied)")
            return True
        
        logger.info(f"🔄 Running: {description}")
        logger.info(f"📁 File: {migration_name}")
        logger.info(f"🎯 Target schema: {self.schema}")
        
        try:
            # Read migration file and replace TARGET_SCHEMA placeholder
            with open(file_path, 'r') as f:
                migration_sql = f.read()
            
            # Replace TARGET_SCHEMA with actual schema name
            processed_sql = migration_sql.replace('TARGET_SCHEMA', self.schema)
            
            # Execute the processed SQL
            result = subprocess.run([
                'psql', self.database_url, '-c', processed_sql
            ], capture_output=True, text=True, check=True)
            
            # Mark as successful
            self.mark_migration_applied(migration_name, True)
            logger.info(f"✅ Success: {description}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed: {description}")
            logger.error(f"Error output: {e.stderr}")
            
            # Mark as failed
            self.mark_migration_applied(migration_name, False)
            return False
        except Exception as e:
            logger.error(f"❌ Failed to read migration file: {str(e)}")
            self.mark_migration_applied(migration_name, False)
            return False
    
    def get_pending_migrations(self) -> List[Tuple[Path, str]]:
        """Get list of migrations that need to be applied"""
        migrations = [
            ('20241201_143000_add_feedback_system_env.sql', 'Feature 2: User Feedback System'),
            ('20241208_143000_add_processing_stage_env.sql', 'Feature 3: Progress Indicator'),
            ('20241215_143000_add_edit_chains_table_env.sql', 'Feature 1: Follow-up Image Editing'),
        ]
        
        pending = []
        for filename, description in migrations:
            file_path = self.migrations_dir / filename
            if file_path.exists():
                if not self.is_migration_applied(filename):
                    pending.append((file_path, description))
            else:
                logger.warning(f"⚠️  Migration file not found: {filename}")
        
        return pending
    
    def run_all_migrations(self) -> bool:
        """Run all pending migrations"""
        logger.info("🚀 Starting Mizual Database Migrations")
        logger.info("=" * 50)
        
        # Check prerequisites
        if not self.check_psql_available():
            logger.error("❌ psql command not available. Install postgresql-client.")
            return False
        
        # Create migration tracking table
        if not self.create_migration_tracking_table():
            return False
        
        # Get pending migrations
        pending_migrations = self.get_pending_migrations()
        
        if not pending_migrations:
            logger.info("✅ No pending migrations. Database is up to date!")
            return True
        
        logger.info(f"📋 Found {len(pending_migrations)} pending migrations")
        
        # Run each migration
        for file_path, description in pending_migrations:
            success = self.run_migration_file(file_path, description)
            if not success:
                logger.error("❌ Migration failed. Stopping.")
                return False
        
        logger.info("🎉 All migrations completed successfully!")
        return True

def main():
    """Main entry point"""
    try:
        runner = MigrationRunner()
        success = runner.run_all_migrations()
        
        if success:
            logger.info("✅ Database migration completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Database migration failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Migration error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()