"""Request-size and cleanup controls (action plan P04).

Review finding 11: the size check read `Content-Length` and nothing else, so a chunked
request that never declares a length was not counted. A 40 KiB chunked body returned 200
against a 32 KiB limit. The deployed nginx caps API bodies at 64 KiB independently, which
limited the exposure, but the application must not depend on a proxy it does not control.

`BodyLimit` is deliberately raw ASGI rather than an `@app.middleware('http')` function:
only at that level can the request body be counted as it arrives and then replayed to the
application. Memory stays bounded because the running total is checked after every chunk.
"""
import json

MAX_BODY_BYTES = 32 * 1024
MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}
TOO_LARGE = json.dumps({'detail': 'Request is too large'}).encode()


class BodyLimit:
    """Reject a request body over `limit` bytes, however it is framed."""

    def __init__(self, app, limit=MAX_BODY_BYTES):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in MUTATING:
            return await self.app(scope, receive, send)

        declared = scope_header(scope, b'content-length')
        if declared is not None and declared > self.limit:
            return await self._reject(send)

        buffered, received, more = [], 0, True
        while more:
            message = await receive()
            if message['type'] == 'http.disconnect':
                buffered.append(message)
                break
            received += len(message.get('body', b''))
            if received > self.limit:
                return await self._reject(send)
            buffered.append(message)
            more = message.get('more_body', False)

        index = 0

        async def replay():
            nonlocal index
            if index < len(buffered):
                message = buffered[index]
                index += 1
                return message
            return {'type': 'http.disconnect'}

        await self.app(scope, replay, send)

    async def _reject(self, send):
        await send({'type': 'http.response.start', 'status': 413,
                    'headers': [(b'content-type', b'application/json'),
                                (b'content-length', str(len(TOO_LARGE)).encode()),
                                (b'cache-control', b'no-store')]})
        await send({'type': 'http.response.body', 'body': TOO_LARGE})


def scope_header(scope, name):
    """An integer header from a raw ASGI scope, or None when absent or malformed."""
    for key, value in scope.get('headers', []):
        if key.lower() == name:
            try:
                return int(value)
            except ValueError:
                return None
    return None
