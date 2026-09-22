# src/sbsys/_transport/__init__.py
"""Internal transport layer. Not part of the public API.

Modules here own authentication, retrying, error translation and redaction.
Nothing in this package knows what a case or a document is.

There are deliberately no re-exports: importing from
``sbsys._transport.http`` rather than ``sbsys._transport`` makes it obvious at
the import line that internal machinery is being touched. Anything under this
package may change in a patch release.
"""
