#!/usr/bin/env python
import sys
import os
import argparse

# Add the parent directory to sys.path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.database import SessionLocal
from app.utils.embedding import update_all_post_embeddings
from app.core.config import settings

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Update embeddings for all blog posts")
    parser.add_argument('--batch-size', type=int, default=50, help='Number of posts to process in each batch')
    parser.add_argument('--force', action='store_true', help='Force update embeddings even for posts that already have them')
    args = parser.parse_args()
    
    # Check if OpenAI API key is set
    if not settings.OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY environment variable is not set")
        sys.exit(1)
    
    # Get database session
    db = SessionLocal()
    
    try:
        print(f"Starting embedding update process (batch size: {args.batch_size})")
        if args.force:
            print("Force update enabled - will update all embeddings regardless of existing values")
        print(f"This may take some time and will use OpenAI API credits.")
        
        # Update all post embeddings
        update_all_post_embeddings(db, batch_size=args.batch_size, force_update=args.force)
        
        print("Embedding update completed successfully!")
    except Exception as e:
        print(f"Error updating embeddings: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main() 