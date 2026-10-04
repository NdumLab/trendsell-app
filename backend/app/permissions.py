"""The workspace permission matrix (action plan P05).

Roles were previously implied by one check — ``role in {'owner', 'analyst'}`` — spread
through the routes, and the audit log was the only owner-only surface. That does not
survive adding reviewers, exports and review actions, each of which needs a different
answer.

Every permission is named here and granted here. A route asks for a permission, never for
a role, so adding a role is a change to this table rather than to every route. The check
is always server-side: a client cannot assert that it holds a permission.
"""
from fastapi import HTTPException

#: What each permission allows. Kept next to the grants so the matrix documents itself.
PERMISSIONS = {
    'workspace.read': 'Read the workspace: products, evidence, assessments, quotes, watches.',
    'workspace.write': 'Create and change workspace records: investigations, decisions, quotes, watches.',
    'evidence.submit': 'Record dated manual evidence and attach it to a product.',
    'compliance.review': 'Approve, reject or supersede an import-readiness review.',
    'workspace.export': 'Download the complete workspace export.',
    'audit.read': 'Read the workspace audit log.',
    'workspace.admin': 'Change workspace settings and membership.',
}

ROLES = {
    # The person who created the workspace. Everything, including the audit log.
    'owner': set(PERMISSIONS),
    # Does the research and owns the commercial assumptions, but cannot clear a
    # compliance gate — that is the separation the decision gates depend on.
    'analyst': {'workspace.read', 'workspace.write', 'evidence.submit', 'workspace.export'},
    # Reads and records evidence and review decisions; does not edit the investigation.
    'reviewer': {'workspace.read', 'evidence.submit', 'compliance.review'},
    # Read-only.
    'viewer': {'workspace.read'},
}

DENIED = {
    'workspace.write': 'Your workspace role is read-only.',
    'evidence.submit': 'Your workspace role cannot record evidence.',
    'compliance.review': 'Import readiness can only be resolved by a workspace reviewer.',
    'workspace.export': 'Your workspace role cannot export the workspace.',
    'audit.read': 'Owner access required.',
    'workspace.admin': 'Owner access required.',
}


def granted(role, permission):
    return permission in ROLES.get(role, set())


def require(user, permission):
    """Raise 403 unless `user`'s role holds `permission`."""
    if permission not in PERMISSIONS:
        raise ValueError(f'unknown permission: {permission}')
    if not granted(user.role, permission):
        raise HTTPException(403, DENIED.get(permission, 'Your workspace role does not allow this.'))
    return user


def matrix():
    """The whole table, for documentation and for the settings screen."""
    return {'permissions': PERMISSIONS,
            'roles': {role: sorted(held) for role, held in ROLES.items()}}
