"""
Sound system for A-MAZE-ING.

Loads .wav files from a "sounds/" folder next to this file.
If a file is missing or pygame.mixer fails, that sound is silently
skipped — the game always runs even without sound files.

Expected files (all short, mono, low-bitrate .wav):
    sounds/step_p1.wav   — P1 footstep (soft click / tap)
    sounds/step_p2.wav   — P2 footstep (slightly different pitch)
    sounds/teleport.wav  — player teleported (sync penalty / intruder eviction)
    sounds/handoff.wav   — stripe ownership changes colour
    sounds/finish.wav    — both players reach the exit

HOW TO RECORD YOUR OWN SOUNDS
------------------------------
You don't need a studio. A phone microphone in a quiet room is fine.

Recommended free tools:
  * Audacity  (desktop, Windows / Mac / Linux)  https://www.audacityteam.org
  * GarageBand (Mac / iOS)
  * Voice Memos (iPhone) or Recorder (Android) — then trim in Audacity

What to record for each sound:

  step_p1.wav / step_p2.wav
    A very short soft tap — fingernail on a wooden desk, tongue click,
    or a muted drum tap.  Aim for 50–120 ms total length.
    Pitch step_p2 slightly higher or lower than step_p1 so players
    can tell them apart with eyes closed.
    Export as: WAV, 44100 Hz, 16-bit mono.

  teleport.wav
    A short descending "whoosh" or a reversed cymbal crash, about
    300–500 ms.  Should feel like being yanked backward.

  handoff.wav
    A short rising "ping" or a bell tap, about 150–300 ms.
    Should feel like a reward / positive transition.

  finish.wav
    A short triumphant chime or flourish, 0.5–2 seconds.

Audacity quick workflow:
  1. Record → trim silence with Edit > Clip Boundaries > Trim
  2. Normalize to -3 dB (Effect > Normalize)
  3. Export as WAV: File > Export > Export as WAV
     Format: WAV (Microsoft), Encoding: Signed 16-bit PCM
  4. Save to the sounds/ folder next to this file.

Volume and pitch can be adjusted here in code (see load() calls below)
without re-recording.
"""

import os
import pygame

_HERE   = os.path.dirname(os.path.abspath(__file__))
_FOLDER = os.path.join(_HERE, "sounds")

# Populated by init(); values are pygame.mixer.Sound or None.
_sounds: dict = {}


def init() -> None:
    """
    Initialise the mixer and load all sound files.
    Call this once after pygame.init(), before the game loop starts.
    """
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
    except pygame.error:
        return   # no audio device — everything stays None

    _load("step_p1",  "step_p1.wav",  volume=0.25)
    _load("step_p2",  "step_p2.wav",  volume=0.25)
    _load("step_ch",  "step_ch.wav",  volume=0.20)
    _load("teleport", "teleport.wav", volume=0.55)
    _load("handoff",  "handoff.wav",  volume=0.50)
    _load("finish",   "finish.wav",   volume=0.70)


def _load(name: str, filename: str, volume: float = 1.0) -> None:
    path = os.path.join(_FOLDER, filename)
    if not os.path.isfile(path):
        _sounds[name] = None
        return
    try:
        sound = pygame.mixer.Sound(path)
        sound.set_volume(volume)
        _sounds[name] = sound
    except pygame.error:
        _sounds[name] = None


def play(name: str) -> None:
    """Play a sound by name. Silent no-op if the file was not found."""
    sound = _sounds.get(name)
    if sound is not None:
        sound.play()
