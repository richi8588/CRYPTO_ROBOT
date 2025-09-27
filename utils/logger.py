
import logging
import sys

def setup_logger():
    """Configures and returns a logger for the application."""
    # Get the root logger
    logger = logging.getLogger("CryptoRobot")
    logger.setLevel(logging.INFO)

    # Prevent logger from propagating to the root logger if it's already configured
    if logger.hasHandlers():
        return logger

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File Handler
    file_handler = logging.FileHandler('robot.log', mode='a')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Create a single logger instance to be used across the application
log = setup_logger()
