import librosa
import json
import sys
import os
import numpy as np
from typing import List, Dict, Tuple

def analyze_audio_features(y: np.ndarray, sr: int) -> Tuple[np.ndarray, float]:
    """
    Analyze audio features to determine energy levels and dynamic changes.
    Returns energy array and average energy.
    """
    # Get the RMS energy for each frame
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

    # Get spectral centroid (brightness/intensity)
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

    # Normalize and combine features for overall energy metric
    rms_normalized = librosa.util.normalize(rms)
    spec_normalized = librosa.util.normalize(spectral_centroids)

    energy = (rms_normalized + spec_normalized) / 2
    average_energy = np.mean(energy)

    return energy, average_energy

def determine_segment_points(beat_times: np.ndarray, energy: np.ndarray,
                           average_energy: float, sr: int, audio_duration: float) -> List[Dict]:
    """
    Determine optimal segmentation points based on energy levels and musical structure,
    ensuring total duration matches audio length.

    Parameters:
        beat_times: Array of beat timestamps
        energy: Array of energy values
        average_energy: Average energy level
        sr: Sample rate
        audio_duration: Total duration of audio file in seconds
    """
    segments = []
    min_segment_beats = 1  # Minimum segment length in beats

    # Convert energy array to beat-aligned
    energy_beats = librosa.util.sync(energy.reshape(1, -1),
                                   librosa.time_to_frames(beat_times, sr=sr),
                                   aggregate=np.mean)[0]

    # Calculate energy changes between beats
    energy_changes = np.abs(np.diff(energy_beats))
    energy_changes = np.append(energy_changes, energy_changes[-1])  # Pad last value

    # Initialize variables for segmentation
    current_start = 0
    current_length = 0
    total_duration = 0

    for i in range(len(beat_times) - 1):
        current_length += 1
        next_segment_duration = beat_times[i + 1] - beat_times[current_start]

        # Check if adding this beat would exceed audio duration
        if total_duration + next_segment_duration > audio_duration:
            # Calculate remaining time
            remaining_time = audio_duration - total_duration
            if remaining_time >= 1.0:  # Only create segment if at least 1 second remains
                segment = {
                    "start": float(beat_times[current_start]),
                    "end": float(beat_times[current_start] + remaining_time),
                    "duration": float(remaining_time),
                    "beats": current_length,
                    "segment_number": len(segments) + 1,
                    "energy_level": float(np.mean(energy_beats[current_start:i + 1]))
                }
                segments.append(segment)
            break

        # Normal segmentation conditions
        should_segment = (
            (energy_changes[i] > np.mean(energy_changes) * 1.5 and current_length >= min_segment_beats) or
            current_length >= 16 or
            (current_length in [4, 8] and energy_changes[i] > np.mean(energy_changes))
        )

        if should_segment:
            segment_duration = beat_times[i + 1] - beat_times[current_start]

            # Create segment
            segment = {
                "start": float(beat_times[current_start]),
                "end": float(beat_times[i + 1]),
                "duration": float(segment_duration),
                "beats": current_length,
                "segment_number": len(segments) + 1,
                "energy_level": float(np.mean(energy_beats[current_start:i + 1]))
            }
            segments.append(segment)

            # Update total duration
            total_duration += segment_duration

            # Reset for next segment
            current_start = i + 1
            current_length = 0

    # Validate total duration
    total_segment_duration = sum(segment["duration"] for segment in segments)
    if abs(total_segment_duration - audio_duration) > 0.1:  # Allow 0.1s tolerance
        print(f"Warning: Total segment duration ({total_segment_duration:.2f}s) "
              f"differs from audio duration ({audio_duration:.2f}s)")

    return segments

def analyze_audio(file_path: str) -> Dict:
    """
    Analyze audio file and create intelligent segmentation based on energy and beats.
    """
    # Load the audio file
    y, sr = librosa.load(file_path)

    # Calculate audio duration
    audio_duration = librosa.get_duration(y=y, sr=sr)

    # Get tempo and beat frames
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Analyze energy and features
    energy, average_energy = analyze_audio_features(y, sr)

    # Generate segments based on analysis
    segments = determine_segment_points(beat_times, energy, average_energy, sr, audio_duration)

    return {
        "file_name": os.path.basename(file_path),
        "tempo": float(tempo),
        "duration": float(audio_duration),
        "total_beats": len(beat_times),
        "average_energy": float(average_energy),
        "segments": segments
    }

def save_analysis(analysis: Dict, audio_path: str) -> str:
    """
    Save analysis results to a JSON file with the same name as the audio file.
    """
    json_path = os.path.splitext(audio_path)[0] + '.json'
    with open(json_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    return json_path

def main():
    if len(sys.argv) != 2:
        print("Usage: python audio_analyzer.py <audio_file_path>")
        sys.exit(1)

    audio_path = sys.argv[1]

    if not os.path.exists(audio_path):
        print(f"Error: File '{audio_path}' not found")
        sys.exit(1)

    try:
        analysis = analyze_audio(audio_path)
        json_path = save_analysis(analysis, audio_path)

        print(f"Analysis complete! Results saved to: {json_path}")
        print(f"Detected tempo: {analysis['tempo']:.1f} BPM")
        print(f"Total beats: {analysis['total_beats']}")
        print(f"Generated segments: {len(analysis['segments'])}")
        print(f"Average energy level: {analysis['average_energy']:.2f}")

    except Exception as e:
        print(f"Error analyzing audio: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()