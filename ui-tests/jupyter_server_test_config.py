"""Jupyter server config for Galata UI tests.

Disables auth + XSRF so Playwright can drive a clean lab without juggling
tokens, locks the port, and points the workspace at this directory so test
files can write fixture notebooks alongside the spec.
"""

c = get_config()  # noqa: F821

c.ServerApp.port = 8888
c.ServerApp.port_retries = 0
c.ServerApp.open_browser = False

c.ServerApp.token = ""
c.ServerApp.password = ""
c.ServerApp.disable_check_xsrf = True
c.LabApp.expose_app_in_browser = True
