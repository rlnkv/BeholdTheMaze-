"""
NEW FILE (this iteration).

Level 1 — Nordic Forest: plain race, no extra mechanics.

ELI5: this is the "base car" with no extra add-ons. We don't need to
override ANY hook methods because level 1 doesn't do anything
special beyond what challenge/base.py already does.
"""

from challenge.base import ChallengeRenderer


class Level1Renderer(ChallengeRenderer):
    """Plain race after memorizing the path. No collectables, no chaser."""

    LEVEL_NUMBER = 1
    LEVEL_NAME = "Nordic Forest"
    MAZE_SIZE = (20, 20)
    PALETTE_INDEX = 3   # "Nordic Forest" palette