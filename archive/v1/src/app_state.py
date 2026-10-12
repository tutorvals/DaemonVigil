"""Global app state - avoids __main__ vs main module import issues."""

_app_instance = None


def set_instance(app):
    global _app_instance
    _app_instance = app


def get_instance():
    return _app_instance
