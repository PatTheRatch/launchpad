"""Display hardware abstraction for Launchpad.

A display only knows how to show a :class:`~launchpad.rendering.frame.Frame`.
This isolates hardware concerns so the rest of the app can run against a mock
display on any machine and swap in real e-ink hardware on the Raspberry Pi.
"""
