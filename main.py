#!/usr/bin/env python3
"""
Main entry point for Fraternity Treasurer App on Replit
"""

# Import the Flask app
from app import app

if __name__ == '__main__':
    # Replit automatically sets the PORT environment variable
    import os
    port = int(os.environ.get('PORT', 8080))
    
    print("🏛️ Starting Fraternity Treasurer App...")
    print(f"📡 Running on port {port}")
    print("🔑 Default login: admin / admin123")
    print("✨ Enhanced features available!")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)