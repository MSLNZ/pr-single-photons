"""
Play WAV tones.
"""
import wave
from enum import Enum
from io import BytesIO
from random import choice
try:
    import winsound
except ImportError:
    # ReadTheDocs uses linux to build to docs, so winsound is not available
    winsound = None

import numpy as np


def _freq(i, j):
    return 440 * (2 ** ((i + (j * 12) - 57) / 12))


SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

NOTES: dict[str, float] = dict(
    (f'{note}{octave}', _freq(i, octave))
    for octave in range(11)
    for i, note in enumerate(SHARPS)
)

NOTES.update(dict(
    (f'{note}{octave}', _freq(i, octave))
    for octave in range(11)
    for i, note in enumerate(FLATS)
))


class Themes(Enum):
    """Short theme clips to play as a WAV file."""

    MARIO = 'mario'
    """Mario completes a level."""

    TETRIS = 'tetris'
    """The Tetris theme."""

    CONTRA = 'contra'
    """The Jungle theme from Contra."""


class Song:

    def __init__(self,
                 sample_rate: float = 44100,
                 tempo: float = 100) -> None:
        """Create a song.

        Args:
            sample_rate: The sample rate, in Hz.
            tempo: The tempo (beats per minute). This parameter creates
                class-instance constants that can be useful when adding notes
                and rests.
        """
        self._sample_rate = sample_rate
        self._frames = []

        self.QUARTER = 60 / tempo  # in seconds
        self.HALF = 2 * self.QUARTER
        self.WHOLE = 2 * self.HALF
        self.EIGHTH = self.QUARTER / 2
        self.SIXTEENTH = self.EIGHTH / 2
        self.DOTTED_WHOLE = 1.5 * self.WHOLE
        self.DOTTED_HALF = 1.5 * self.HALF
        self.DOTTED_QUARTER = 1.5 * self.QUARTER
        self.DOTTED_EIGHTH = 1.5 * self.EIGHTH
        self.DOTTED_SIXTEENTH = 1.5 * self.SIXTEENTH

    def add(self,
            duration: float,
            left: str | list[str] = None,
            right: str | list[str] = None,
            volume: float = 0.5) -> None:
        """Add a rest, note or chord to the song.

        Args:
            duration: The number of seconds the note will play for, or, the
                number of seconds to rest.
            left: The name(s) of the note(s) to add to the left channel
                (e.g., 'A4' or ['C4', 'G3', 'E3'] for a chord). Do not specify
                a value to add a rest.
            right: The name(s) of the note(s) to add to the right channel
                (e.g., 'C3'). If not specified then equals the left channel.
            volume: The amplitude of the sine wave. Should be between 0 and 1.
        """
        n = round(self._sample_rate * duration)
        left_channel = np.zeros(n)
        right_channel = np.zeros(n)
        if left:
            t = np.linspace(0, duration, n)

            if isinstance(left, str):
                left = [left]

            amplitude = volume / len(left)
            for note in left:
                left_channel += amplitude * np.cos(2 * np.pi * NOTES[note] * t)

            if right is None:
                right_channel = left_channel
            else:
                if isinstance(right, str):
                    right = [right]

                amplitude = volume / len(right)
                for note in right:
                    right_channel += amplitude * np.cos(2 * np.pi * NOTES[note] * t)

        channels = np.vstack((left_channel, right_channel)).T
        self._frames.append(channels)

    def play(self) -> None:
        """Play the song."""
        with BytesIO() as buffer:
            with wave.open(buffer, mode='w') as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(self._sample_rate)
                for frame in self._frames:
                    # convert to (little-endian) 16-bit integer
                    audio = (frame * (2 ** 15 - 1)).astype('<h')
                    w.writeframes(audio.tobytes())
            winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY)


def play(wav: str | Themes, wait: bool = True) -> None:
    """Play a WAV file or theme.

    Args:
        wav: The file or theme to play.
        wait: Whether to wait for the WAV file to finish playing before returning.
            Only used if `wav` is a file. Specifying one of the :class:`Themes`
            will always wait, since the audio data is stored in memory.
    """
    if wav == Themes.MARIO:
        song = Song(tempo=400)
        song.add(song.QUARTER, 'C3')
        song.add(song.QUARTER, 'C4')
        song.add(song.QUARTER, 'E4')
        song.add(song.QUARTER, 'G4')
        song.add(song.QUARTER, 'C5')
        song.add(song.QUARTER, 'E5')
        song.add(song.HALF, 'G5')
        song.add(song.HALF, 'E5')
        song.add(song.QUARTER, 'D3')
        song.add(song.QUARTER, 'C4')
        song.add(song.QUARTER, 'D#4')
        song.add(song.QUARTER, 'G#4')
        song.add(song.QUARTER, 'C5')
        song.add(song.QUARTER, 'D#5')
        song.add(song.HALF, 'G#5')
        song.add(song.HALF, 'D#5')
        song.add(song.QUARTER, 'D#3')
        song.add(song.QUARTER, 'D4')
        song.add(song.QUARTER, 'F4')
        song.add(song.QUARTER, 'A#4')
        song.add(song.QUARTER, 'D5')
        song.add(song.QUARTER, 'F5')
        song.add(song.HALF, 'A#5')
        song.add(song.QUARTER, 'A#5')
        song.add(song.QUARTER, 'A#5')
        song.add(song.QUARTER, 'A#5')
        song.add(song.WHOLE, 'C6')
        song.play()
    elif wav == Themes.TETRIS:
        song = Song(tempo=160)
        song.add(song.QUARTER, 'E5', 'E4')
        song.add(song.EIGHTH, 'B4', 'B3')
        song.add(song.EIGHTH, 'C5', 'C4')
        song.add(song.QUARTER, 'D5', 'D4')
        song.add(song.EIGHTH, 'C5', 'C4')
        song.add(song.EIGHTH, 'B4', 'B3')
        song.add(song.QUARTER, 'A4', 'A3')
        song.add(song.EIGHTH, 'A4', 'A3')
        song.add(song.EIGHTH, 'C5', 'C4')
        song.add(song.QUARTER, 'E5', 'E4')
        song.add(song.EIGHTH, 'D5', 'D4')
        song.add(song.EIGHTH, 'C5', 'C4')
        song.add(song.QUARTER, 'B4', 'B3')
        song.add(song.EIGHTH, 'B4', 'B3')
        song.add(song.EIGHTH, 'C5', 'C4')
        song.add(song.QUARTER, 'D5', 'D4')
        song.add(song.QUARTER, 'E5', 'E4')
        song.add(song.QUARTER, 'C5', 'C4')
        song.add(song.QUARTER, 'A4', 'A3')
        song.add(song.QUARTER, 'A4', 'A3')
        song.play()
    elif wav == Themes.CONTRA:
        song = Song(tempo=150)
        song.add(song.SIXTEENTH, 'F5')
        song.add(song.SIXTEENTH, 'Eb5')
        song.add(song.SIXTEENTH, 'C5')
        song.add(song.SIXTEENTH, 'Bb4')
        song.add(song.SIXTEENTH, 'C5')
        song.add(song.SIXTEENTH, 'B4')
        song.add(song.SIXTEENTH, 'Ab4')
        song.add(song.SIXTEENTH, 'G4')
        song.add(song.SIXTEENTH, 'A4')
        song.add(song.SIXTEENTH, 'G4')
        song.add(song.SIXTEENTH, 'F4')
        song.add(song.SIXTEENTH, 'Eb4')
        song.add(song.SIXTEENTH, 'F4')
        song.add(song.SIXTEENTH, 'Bb3')
        song.add(song.SIXTEENTH, 'C4')
        song.add(song.SIXTEENTH, 'E4')
        song.add(song.HALF, 'F4')
        song.add(song.SIXTEENTH)
        song.add(song.SIXTEENTH, 'C5')
        song.add(song.SIXTEENTH, 'Bb4')
        song.add(song.SIXTEENTH, 'C5')
        song.add(song.SIXTEENTH, 'D5')
        song.add(song.HALF, 'Eb5')
        song.play()
    else:
        # assume it's a file
        flags = winsound.SND_FILENAME
        if not wait:
            flags |= winsound.SND_ASYNC
        winsound.PlaySound(wav, flags)


def random() -> None:
    """Play a random theme."""
    play(choice(list(Themes.__members__.values())))
