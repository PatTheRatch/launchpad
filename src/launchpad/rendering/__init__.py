"""Rendering for Launchpad.

Renderers turn a :class:`~launchpad.models.dashboard.DashboardState` into a
:class:`~launchpad.rendering.frame.Frame`. They are independent of both data
retrieval (they only read models) and display hardware (they only produce a
neutral frame). Orientation-specific layouts live in their own modules.
"""
