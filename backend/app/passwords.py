"""Password hashing with an upgradeable, self-describing format (action plan P02).

Review finding 9: passwords were scrypt with ``N=2^14, r=8, p=1`` — below every
configuration OWASP lists — and the stored value was only ``salt:digest``, so raising the
parameters would have invalidated every existing password at once.

The stored value now names its own algorithm and parameters:

    scrypt$n=65536,r=8,p=2$<salt hex>$<digest hex>

so a future change is a new prefix rather than a lockout. ``N=2^16 (64 MiB), r=8, p=2`` is
one of the five equivalent parameter sets in the OWASP Password Storage Cheat Sheet; it was
chosen over ``N=2^17, r=8, p=1`` because the two cost the same but this one needs half the
peak memory per concurrent login, which matters on a shared host.
Source: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

The legacy format still verifies, and a correct sign-in rehashes it — the transition OWASP
describes. No existing user is locked out, and nobody has to reset a password.
"""
import hashlib
import hmac
import secrets

ALGORITHM = 'scrypt'
PARAMETERS = {'n': 2 ** 16, 'r': 8, 'p': 2}
#: The parameters every pre-P02 hash was produced with. Kept so those hashes still verify.
LEGACY_PARAMETERS = {'n': 2 ** 14, 'r': 8, 'p': 1}
SALT_BYTES = 16


def _derive(password, salt, parameters):
    # OpenSSL caps scrypt memory at 32 MiB unless maxmem is raised, and these parameters
    # need more than that; the formula is the documented buffer requirement.
    maxmem = 128 * parameters['n'] * parameters['r'] * (parameters['p'] + 2)
    # The salt is fed as the ASCII bytes of its hex form — 128 bits of entropy in 32
    # characters — because that is what the legacy hashes used. Keeping one derivation
    # path means a legacy hash verifies without a second implementation to get wrong.
    return hashlib.scrypt(password.encode(), salt=salt.encode(),
                          n=parameters['n'], r=parameters['r'], p=parameters['p'],
                          maxmem=maxmem).hex()


def hash_password(password, salt=None, parameters=None):
    """A new hash in the current format."""
    parameters = parameters or PARAMETERS
    salt = salt or secrets.token_hex(SALT_BYTES)
    digest = _derive(password, salt, parameters)
    encoded = ','.join(f'{key}={parameters[key]}' for key in ('n', 'r', 'p'))
    return f'{ALGORITHM}${encoded}${salt}${digest}'


def parse(stored):
    """(parameters, salt, digest, is_legacy) for a stored hash, or None if unreadable."""
    if stored.startswith(f'{ALGORITHM}$'):
        try:
            _, encoded, salt, digest = stored.split('$', 3)
            parameters = {key: int(value) for key, value in
                          (pair.split('=', 1) for pair in encoded.split(','))}
            if set(parameters) != {'n', 'r', 'p'}:
                return None
            return parameters, salt, digest, False
        except (ValueError, KeyError):
            return None
    # Legacy: '<salt hex>:<digest hex>' at the original parameters.
    salt, separator, digest = stored.partition(':')
    if not separator or not salt or not digest:
        return None
    return LEGACY_PARAMETERS, salt, digest, True


def verify_password(password, stored):
    """(ok, needs_rehash). `needs_rehash` is True for a legacy or weaker-than-current hash."""
    parsed = parse(stored)
    if parsed is None:
        return False, False
    parameters, salt, digest, is_legacy = parsed
    try:
        candidate = _derive(password, salt, parameters)
    except (ValueError, MemoryError):
        return False, False
    if not hmac.compare_digest(candidate, digest):
        return False, False
    return True, is_legacy or parameters != PARAMETERS


def dummy_verify(password):
    """Spend comparable work when the account does not exist, so timing tells nothing."""
    hash_password(password)
