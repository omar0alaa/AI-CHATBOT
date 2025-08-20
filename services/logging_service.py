# Logging service - Centralized logging functionality

import logging
import os
from datetime import datetime


class LoggingService:
    #Centralized logging service for the chatbot application
    
    def __init__(self):
        self.logger_name = 'chatbot_debug'
        self.logger = None
        self.setup_logger()
    
    def setup_logger(self):
        #Setup logger that writes to console and file only when debug mode is enabled
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Only add handlers when debug is enabled
        debug_enabled = os.environ.get("SHOW_DEBUG", "false").lower() == "true"
        if debug_enabled:
            # Console handler (only when debug enabled)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_format = logging.Formatter('%(message)s')
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)
            
            # File handler (only when debug enabled)
            if not os.path.exists('logs'):
                os.makedirs('logs')
            
            log_filename = f"logs/chatbot_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter('%(asctime)s - %(message)s')
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        
        return self.logger
    
    def debug(self, message):
        #Log debug message to console and file (if debug enabled)
        if self.logger:
            self.logger.debug(f"[DEBUG] {message}")
    
    def post_process(self, message):
        #Log PostProcess message to console and file (if debug enabled)
        if self.logger:
            self.logger.debug(f"[PostProcess] {message}")
    
    def info(self, message):
        #Log info message to console and file (if debug enabled)
        if self.logger:
            self.logger.info(f"[INFO] {message}")
    
    def warning(self, message):
        #Log warning message to console and file (if debug enabled)
        if self.logger:
            self.logger.warning(f"[WARNING] {message}")
    
    def error(self, message):
        #Log error message to console and file (if debug enabled)
        if self.logger:
            self.logger.error(f"[ERROR] {message}")
    
    def update_logger(self):
        #Update logger configuration when debug mode is toggled
        self.setup_logger()
    
    def is_debug_enabled(self):
        #Check if debug mode is currently enabled
        return os.environ.get("SHOW_DEBUG", "false").lower() == "true"


# Create a global logger instance
logging_service = LoggingService()

# Convenience functions for backward compatibility
def log_debug(message):
    #Log debug message
    logging_service.debug(message)

def log_post_process(message):
    #Log PostProcess message
    logging_service.post_process(message)

def log_info(message):
    #Log info message
    logging_service.info(message)

def log_warning(message):
    #Log warning message
    logging_service.warning(message)

def log_error(message):
    #Log error message
    logging_service.error(message)

def setup_logger():
    #Setup logger - for backward compatibility
    return logging_service.setup_logger()

def update_logger():
    #Update logger configuration
    logging_service.update_logger()

def is_debug_enabled():
    #Check if debug mode is enabled
    return logging_service.is_debug_enabled()
