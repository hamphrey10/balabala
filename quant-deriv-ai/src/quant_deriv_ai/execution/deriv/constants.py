"""Official Deriv WebSocket API constants.

Sources:
- https://api.deriv.com (register app_id + API tokens)
- https://github.com/deriv-com/deriv-api — ``wss://ws.derivws.com/websockets/v3?app_id=…``
- https://deriv-com.github.io/python-deriv-api/ — ``authorize``, ``balance``, ``ping``
"""

from __future__ import annotations

# Official production WebSocket host + path (app_id is a query parameter).
DEFAULT_DERIV_ENDPOINT = "wss://ws.derivws.com/websockets/v3"

# Documented public test app_id from Deriv samples (register your own at api.deriv.com).
DEFAULT_TEST_APP_ID = "1089"

# authorize.is_virtual: 1 = virtual/demo, 0 = real.
IS_VIRTUAL_DEMO = 1
IS_VIRTUAL_REAL = 0
