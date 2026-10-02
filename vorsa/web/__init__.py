"""Weboberflaeche fuer VORSA-M3.

Bewusst ohne Fremdbibliotheken - nur http.server aus der Standardbibliothek.
Auf dem Pi muss dafuer nichts nachinstalliert werden, und es gibt keine
Version, die zu MetaTF passen muss.
"""
__all__ = ["server", "state"]
