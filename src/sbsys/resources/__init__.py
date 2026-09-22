# src/sbsys/resources/__init__.py
"""The resource layer: one module per SBSYS domain area.

Resources build requests and parse responses. They know about models and the
transport, and nothing about HTTP mechanics. They are instantiated by
:class:`~sbsys.client.SbsysClient` and reached as attributes on it, never
constructed directly.

Method names use the Danish domain vocabulary — ``sag``, ``journalnotat``,
``erindring`` — because these terms have no good English equivalents and match
what SBSYS, the caseworkers and the legislation call them. Documentation is in
English.
"""
