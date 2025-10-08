#!/usr/bin/env python3
"""
Apply database migration for full text content support.
"""

import os

def apply_migration():
    """Apply the full text migration."""
    
    # Read migration SQL
    migration_path = "database/migrations/001_add_full_text_column.sql"
    
    if not os.path.exists(migration_path):
        print(f"Migration file not found: {migration_path}")
        return False
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    print("Database Migration: Add full_text columns to articles table")
    print("=" * 60)
    print(migration_sql)
    print("=" * 60)
    
    print("\n⚠️  MANUAL ACTION REQUIRED:")
    print("Please copy the above SQL and run it in your Supabase SQL Editor:")
    print("1. Go to https://supabase.com/dashboard/project/[your-project]/sql")
    print("2. Paste the SQL above")
    print("3. Click 'Run'")
    print("\nAfter running the migration, you can test the content fetching with:")
    print("python run.py content status --hours 24")
    
    return True

if __name__ == "__main__":
    success = apply_migration()
    exit(0 if success else 1)
