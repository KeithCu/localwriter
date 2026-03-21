import os

def get_plugin_dir():
    """Returns the absolute path to the plugin/ directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
