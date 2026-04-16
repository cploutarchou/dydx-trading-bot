#!/usr/bin/env python3
"""Comprehensive validation check"""

import inspect

from src.api.server import app
from src.infrastructure.database import get_session

print('=== DATABASE SESSION DEPENDENCY VALIDATION ===\n')

# Check if get_session is a generator
sig = inspect.signature(get_session)
source = inspect.getsource(get_session)

print('get_session function signature:')
print(f'  Parameters: {list(sig.parameters.keys())}')
print(f'  Return annotation: {sig.return_annotation}')

print('\nChecking for cleanup pattern...')
if 'yield' in source:
    print('  ✓ Uses yield (proper generator cleanup)')
else:
    print('  ✗ Does not use yield (missing cleanup)')

if 'finally' in source:
    print('  ✓ Has finally block')
else:
    print('  ⚠ No finally block')

if 'session.close()' in source:
    print('  ✓ Explicitly closes session')
else:
    print('  ✗ Missing session.close()')

# Check API routes for session handling
print('\n=== REALTIME ROUTE SESSION HANDLING ===\n')

realtime_route_names = [
    'get_position',
    'get_current_positions',
    'get_market_data',
    'get_realtime_stats',
    'get_alerts',
    'get_position_history',
]

for route in app.routes:
    if hasattr(route, 'name') and route.name in realtime_route_names:
        if hasattr(route, 'endpoint'):
            endpoint_source = inspect.getsource(route.endpoint)
            has_session_close = 'session.close()' in endpoint_source
            has_finally = 'finally' in endpoint_source
            has_auth = 'get_current_active_user' in endpoint_source

            status = []
            if has_auth:
                status.append('auth')
            else:
                status.append('X-no-auth')

            if has_finally and has_session_close:
                status.append('cleanup')
            else:
                status.append('X-no-cleanup')

            status_str = ' / '.join(status)
            print(f'{route.name:25} {status_str}')

print('\n=== SESSION VALIDATION COMPLETE ===')
