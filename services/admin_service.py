# Admin service - Handles admin-related business logic

import os
from logger import log_info, setup_logger


class AdminService:
    # Service class for admin operations
    
    def toggle_debug_mode(self):
        # Toggle debug mode on/off
        current_debug = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
        new_debug = not current_debug
        os.environ["SHOW_DEBUG"] = "true" if new_debug else "false"
        
        # Reinitialize logger with new debug setting
        setup_logger()
        
        if new_debug:
            log_info("Debug mode enabled - logging to file started")
        else:
            log_info("Debug mode disabled - file logging stopped")
        
        return {
            'debug_enabled': new_debug,
            'message': f"Debug mode {'enabled' if new_debug else 'disabled'}"
        }
    
    def get_debug_status(self):
        # Get current debug status
        current_debug = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
        return {'debug_enabled': current_debug}


# Create singleton instance
admin_service = AdminService()
