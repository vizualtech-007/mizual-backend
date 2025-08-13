#!/usr/bin/env python3
"""
Migration script for Render deployment
Runs database migrations using environment variables from Render
"""

import os
import subprocess
import sys
from pathlib import Path

def run_migration_file(file_path, description):
    """Run a single migration file"""
    print(f"Running: {description}")
    print(f"File: {file_path}")
    
    # Get database URL from environment (Render sets this automatically)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        return False
    
    try:
        # Run psql with the migration file
        result = subprocess.run([
            'psql', database_url, '-f', file_path
        ], capture_output=True, text=True, check=True)
        
        print(f"✅ Success: {description}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ psql command not found. PostgreSQL client not installed.")
        return False

def main():
    """Run all migrations in order"""
    print("🚀 Starting Mizual Database Migrations on Render")
    print("=" * 50)
    
    # Check if we're in the right directory
    migrations_dir = Path(__file__).parent / 'migrations'
    if not migrations_dir.exists():
        migrations_dir = Path('migrations')
    
    if not migrations_dir.exists():
        print("❌ Migrations directory not found")
        sys.exit(1)
    
    # Migration files in order
    migrations = [
        ('20241201_143000_add_feedback_system.sql', 'Feature 2: User Feedback System'),
        ('20241208_143000_add_processing_stage.sql', 'Feature 3: Progress Indicator'),
        ('20241215_143000_add_edit_chains_table.sql', 'Feature 1: Follow-up Image Editing'),
    ]
    
    # Run each migration
    for filename, description in migrations:
        file_path = migrations_dir / filename
        if not file_path.exists():
            print(f"❌ Migration file not found: {file_path}")
            sys.exit(1)
        
        success = run_migration_file(str(file_path), description)
        if not success:
            print("❌ Migration failed. Stopping.")
            sys.exit(1)
        print()
    
    print("🎉 All migrations completed successfully!")
    print("\nNext steps:")
    print("1. Deploy your updated backend code")
    print("2. Implement Feature 2 (Feedback System)")
    print("3. Then Feature 3 (Progress Indicator)")
    print("4. Finally Feature 1 (Follow-up Editing)")

if __name__ == "__main__":
    main()