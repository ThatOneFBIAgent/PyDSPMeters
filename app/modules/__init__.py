"""Module registry for all visualization modules."""

MODULE_REGISTRY = {}


def register_module(name, display_name):
    """Decorator to register a module class."""
    def decorator(cls):
        MODULE_REGISTRY[name] = {"class": cls, "display_name": display_name}
        return cls
    return decorator
