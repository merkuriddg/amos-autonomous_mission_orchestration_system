import os

def get_template_dir():
    # Always prefer source tree — guaranteed to have latest files
    src = os.path.expanduser(
        '~/mos_ws/src/mos_c2_console/mos_c2_console/templates')
    if os.path.isdir(src):
        return src
    # Fallback to installed package
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'templates')
