#!/usr/bin/env python
"""
CLI script to dispatch pending webhook events.

Usage:
    python scripts/dispatch_webhooks.py [--limit 100] [--timeout 10]

This script can be run manually or via cron/supervisor for continuous webhook delivery.
"""
import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.events.dispatcher import dispatch_pending_events


def main():
    parser = argparse.ArgumentParser(description='Dispatch pending webhook events')
    parser.add_argument('--limit', type=int, default=100, help='Maximum number of events to process')
    parser.add_argument('--timeout', type=int, default=10, help='HTTP request timeout in seconds')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        if args.verbose:
            print(f"Dispatching up to {args.limit} pending webhook events...")
        
        results = dispatch_pending_events(limit=args.limit, timeout=args.timeout)
        
        print(f"Webhook dispatch complete:")
        print(f"  Processed: {results['processed']}")
        print(f"  Delivered: {results['delivered']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Skipped: {results['skipped']}")
        
        # Exit with non-zero code if there were failures
        if results['failed'] > 0:
            sys.exit(1)


if __name__ == '__main__':
    main()
