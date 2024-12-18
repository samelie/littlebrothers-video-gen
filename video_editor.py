import json
import random
import os
import subprocess
from pathlib import Path
import tempfile
import shlex
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_audio_duration(audio_path):
    """
    Get audio file duration using ffprobe.
    Returns duration in seconds.
    """
    logger.info(f"Getting audio duration for: {audio_path}")

    try:
        duration_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        logger.debug("Executing audio duration command...")
        logger.debug(f"Command: {format_command(duration_cmd)}")

        duration_output = subprocess.check_output(duration_cmd, stderr=subprocess.PIPE)
        logger.debug(f"Duration command raw output: {duration_output}")

        duration = float(duration_output.decode().strip())
        logger.info(f"Audio duration: {duration:.2f} seconds")

        return duration

    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe command failed for {audio_path}")
        logger.error(f"Command output: {e.output.decode() if e.output else 'None'}")
        logger.error(f"Command stderr: {e.stderr.decode() if e.stderr else 'None'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting audio duration for {audio_path}: {str(e)}")
        raise

def format_command(cmd):
    """Format a command list into a readable shell command string"""
    formatted = ' '.join(shlex.quote(str(arg)) for arg in cmd)
    logger.debug(f"Formatted command: {formatted}")
    return formatted

def calculate_crop_params(source_width, source_height, target_width, target_height):
    """
    Calculate scaling and cropping parameters to maintain aspect ratio from center.
    Handles both landscape and portrait videos by scaling up first if needed.
    Returns filter string for ffmpeg
    """
    logger.info(f"Calculating parameters for {source_width}x{source_height} -> {target_width}x{target_height}")

    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    logger.debug(f"Source aspect: {source_aspect:.3f}, Target aspect: {target_aspect:.3f}")

    # First, determine if we need to scale up
    scale_width = source_width
    scale_height = source_height

    # If source dimensions are smaller than target, scale up first
    if source_width < target_width or source_height < target_height:
        # Scale based on the dimension that needs the larger scaling factor
        width_scale = target_width / source_width
        height_scale = target_height / source_height
        scale_factor = max(width_scale, height_scale)

        scale_width = int(source_width * scale_factor)
        scale_height = int(source_height * scale_factor)
        logger.debug(f"Scaling to intermediate size: {scale_width}x{scale_height}")

    # Now calculate crop after scaling
    if source_aspect > target_aspect:
        # Source is wider - crop width
        new_width = int(scale_height * target_aspect)
        crop_x = (scale_width - new_width) // 2
        filter_chain = [
            f"scale={scale_width}:{scale_height}",
            f"crop={new_width}:{scale_height}:{crop_x}:0",
            f"scale={target_width}:{target_height}",
            f"format=yuv420p"
        ]
    elif source_aspect < target_aspect:
        # Source is taller - crop height
        new_height = int(scale_width / target_aspect)
        crop_y = (scale_height - new_height) // 2
        filter_chain = [
            f"scale={scale_width}:{scale_height}",
            f"crop={scale_width}:{new_height}:0:{crop_y}",
            f"scale={target_width}:{target_height}",
            f"format=yuv420p"
        ]
    else:
        # Aspects match - just scale
        filter_chain = [f"scale={target_width}:{target_height}", f"format=yuv420p"]

    filter_string = ','.join(filter_chain)
    logger.info(f"Calculated filter chain: {filter_string}")
    return filter_string



def get_video_info(video_path):
    """
    Get video duration and dimensions using ffprobe.
    Returns (duration, width, height)
    """
    logger.info(f"Getting video info for: {video_path}")

    try:
        # Get duration
        duration_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        logger.debug("Executing duration command...")
        logger.debug(f"Command: {format_command(duration_cmd)}")

        duration_output = subprocess.check_output(duration_cmd, stderr=subprocess.PIPE)
        logger.debug(f"Duration command raw output: {duration_output}")

        duration = float(duration_output.decode().strip())
        logger.info(f"Video duration: {duration:.2f} seconds")

        # Get dimensions
        dimension_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            video_path
        ]
        logger.debug("Executing dimension command...")
        logger.debug(f"Command: {format_command(dimension_cmd)}")

        dimension_output = subprocess.check_output(dimension_cmd, stderr=subprocess.PIPE)
        logger.debug(f"Dimension command raw output: {dimension_output}")

        dimensions = json.loads(dimension_output.decode())
        logger.debug(f"Parsed dimensions JSON: {dimensions}")

        if not dimensions.get('streams'):
            logger.error(f"No video streams found in {video_path}")
            raise ValueError(f"No video streams found in {video_path}")

        width = int(dimensions['streams'][0]['width'])
        height = int(dimensions['streams'][0]['height'])
        logger.info(f"Video dimensions: {width}x{height}")

        return duration, width, height

    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe command failed for {video_path}")
        logger.error(f"Command output: {e.output.decode() if e.output else 'None'}")
        logger.error(f"Command stderr: {e.stderr.decode() if e.stderr else 'None'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing {video_path}: {str(e)}")
        raise

def find_video_files(folders, extensions):
    """
    Recursively find all video files with given extensions in multiple folders and their subfolders.

    Args:
        folders: String of comma-separated folder paths or list of folder paths
        extensions: String of comma-separated file extensions

    Returns:
        A list of full file paths.
    """
    logger.info(f"Searching for videos in multiple folders")

    # Convert folders to list if it's a string
    if isinstance(folders, str):
        folder_list = [f.strip() for f in folders.split(',')]
    else:
        folder_list = folders

    logger.debug(f"Searching in folders: {folder_list}")
    logger.debug(f"Looking for extensions: {extensions}")

    video_files = []
    ext_list = extensions.lower().split(',')

    try:
        for folder in folder_list:
            logger.info(f"Searching in folder: {folder}")
            # Convert to Path object
            folder_path = Path(folder)

            if not folder_path.exists():
                logger.warning(f"Folder does not exist: {folder}")
                continue

            # Search for each extension
            for ext in ext_list:
                # Search lowercase extensions
                files = list(folder_path.rglob(f"*.{ext}"))
                logger.debug(f"Found {len(files)} files with extension .{ext} in {folder}")
                video_files.extend(str(f) for f in files)

                # Search uppercase extensions
                files = list(folder_path.rglob(f"*.{ext.upper()}"))
                logger.debug(f"Found {len(files)} files with extension .{ext.upper()} in {folder}")
                video_files.extend(str(f) for f in files)

        logger.info(f"Found {len(video_files)} total video files across all folders")
        logger.debug("First few files found: " +
                    str(video_files[:5]) +
                    ("..." if len(video_files) > 5 else ""))

        if not video_files:
            logger.warning(f"No videos found in any folders with extensions: {extensions}")

        return video_files

    except Exception as e:
        logger.error(f"Error searching for videos: {str(e)}")
        raise

def run_ffmpeg_command(cmd, input_file, output_file, timeout=60):
    """
    Run an ffmpeg command with proper error handling and timeout
    Returns True if successful, False if timed out or failed
    """
    logger.info(f"Running FFmpeg command for input: {input_file}")
    logger.info(f"Output will be written to: {output_file}")
    logger.debug(f"Full command: {format_command(cmd)}")

    try:
        # Start the FFmpeg process
        logger.debug("Starting FFmpeg process...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        try:
            # Wait for the process with timeout
            logger.debug(f"Waiting for FFmpeg process to complete (timeout: {timeout}s)...")
            stdout, stderr = process.communicate(timeout=timeout)

            if stdout:
                logger.debug(f"FFmpeg stdout: {stdout}")
            if stderr:
                logger.debug(f"FFmpeg stderr: {stderr}")

            if process.returncode != 0:
                logger.error(f"FFmpeg command failed with return code: {process.returncode}")
                logger.error(f"Command was: {format_command(cmd)}")
                logger.error(f"Stdout: {stdout}")
                logger.error(f"Stderr: {stderr}")
                return False

            logger.info("FFmpeg command completed successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.warning(f"FFmpeg command timed out after {timeout} seconds")

            # Kill the process and its children
            try:
                process.kill()
                # Wait a bit for process to be killed
                process.wait(timeout=5)
                logger.info("Successfully killed stuck FFmpeg process")
            except Exception as kill_error:
                logger.error(f"Error killing FFmpeg process: {kill_error}")

            # Clean up the incomplete output file if it exists
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                    logger.info(f"Removed incomplete output file: {output_file}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up output file: {cleanup_error}")

            return False

    except Exception as e:
        logger.error(f"Error running FFmpeg command: {str(e)}")
        return False

def process_segment(segment, i, video_files, temp_dir, output_width, output_height, max_retries=3):
    """
    Process a single segment with retry logic and timestamp handling
    Returns (success, segment_file_path)
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"Processing segment {i+1}, attempt {attempt+1}/{max_retries}")

            # Select random video
            source_video = random.choice(video_files)
            logger.info(f"Selected video: {source_video}")

            # Get video information
            video_duration, source_width, source_height = get_video_info(source_video)

            # Calculate random start point
            max_start = max(0, video_duration - segment['duration'])
            start_time = random.uniform(0, max_start) if max_start > 0 else 0

            # Generate unique identifier
            unique_id = ''.join(random.choices('0123456789abcdef', k=6))
            segment_file = os.path.join(temp_dir, f'segment_video_file_{i}_{unique_id}.mp4')

            # Get filter chain
            filter_string = calculate_crop_params(source_width, source_height, output_width, output_height)

            # Add timestamp correction to filter chain
            filter_string += ',setpts=PTS-STARTPTS'  # Reset timestamps to start at 0

            # Extract segment using ffmpeg with consistent timestamp settings
            extract_cmd = [
                'ffmpeg', '-y',
                '-v', 'warning',
                '-ss', str(start_time),
                '-i', source_video,
                '-t', str(segment['duration']),
                '-vf', filter_string,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-video_track_timescale', '30000',  # Consistent timescale
                '-pix_fmt', 'yuv420p',
                '-color_range', '1',
                '-colorspace', 'bt709',
                '-color_primaries', 'bt709',
                '-color_trc', 'bt709',
                '-force_key_frames', f"expr:gte(t,0+n_forced*{segment['duration']})",  # Force keyframe at start
                '-fps_mode', 'cfr',  # Ensure timestamp consistency
                '-async', '1',  # Audio sync
                '-movflags', '+faststart+empty_moov',
                '-an',  # No audio
                segment_file
            ]

            if run_ffmpeg_command(extract_cmd, source_video, segment_file, timeout=100):
                return True, segment_file

            logger.warning(f"Attempt {attempt+1} failed, trying again...")

        except Exception as e:
            logger.error(f"Error in attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                logger.info("Retrying with different video...")
            continue

    return False, None

import json
import random
import os
import subprocess
from pathlib import Path
import tempfile
import shlex
import sys
import logging

# [Previous imports and logging setup remain the same]

# [Previous helper functions remain the same until create_edited_video]

def create_edited_video(segments_file, video_folder, output_file, output_width, output_height, audio_file=None, extensions="mp4,mov,mkv,avi", temp_dir=None):
    """
    Creates an edited video based on JSON segments file and source videos.
    Optionally includes a custom audio track.

    Args:
        segments_file: Path to JSON file containing segment information
        video_folder: Path to folder or comma-separated list of folders containing source videos
        output_file: Path where the final video should be saved
        output_width: Output video width
        output_height: Output video height
        audio_file: Optional path to audio file to use as soundtrack
        extensions: Comma-separated list of video file extensions to include
        temp_dir: Optional custom temporary directory path. If None, creates a new temp directory
    """
    logger.info(f"Starting video creation process")
    logger.info(f"Segments file: {segments_file}")
    logger.info(f"Video folders: {video_folder}")
    logger.info(f"Output dimensions: {output_width}x{output_height}")

    # Load segments from JSON file
    try:
        logger.debug(f"Reading segments file: {segments_file}")
        with open(segments_file, 'r') as f:
            data = json.load(f)

        if not isinstance(data, dict) or 'segments' not in data:
            logger.error("Invalid JSON structure: missing 'segments' key")
            raise ValueError("JSON file must contain a 'segments' key with an array of segments")

        segments = data['segments']
        logger.info(f"Found {len(segments)} segments from {data.get('file_name', 'unknown source')}")
        logger.info(f"Source tempo: {data.get('tempo', 'unknown')} BPM")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in segments file: {e}")
        raise ValueError(f"Invalid JSON in segments file: {e}")
    except Exception as e:
        logger.error(f"Error reading segments file: {e}")
        raise ValueError(f"Error reading segments file: {e}")

    # Get list of video files recursively
    video_files = find_video_files(video_folder, extensions)

    if not video_files:
        raise ValueError(f"No videos with extensions {extensions} found in {video_folder} or its subdirectories")

    # Context manager for temporary directory handling
    class TempDirManager:
        def __init__(self, custom_temp_dir=None):
            self.custom_temp_dir = custom_temp_dir
            self.temp_dir = None
            self.temp_obj = None

        def __enter__(self):
            if self.custom_temp_dir:
                # Create the custom temp directory if it doesn't exist
                os.makedirs(self.custom_temp_dir, exist_ok=True)
                self.temp_dir = self.custom_temp_dir
                logger.info(f"Using custom temporary directory: {self.temp_dir}")
            else:
                # Create a new temporary directory
                self.temp_obj = tempfile.TemporaryDirectory()
                self.temp_dir = self.temp_obj.name
                logger.info(f"Created temporary directory: {self.temp_dir}")
            return self.temp_dir

        def __exit__(self, exc_type, exc_val, exc_tb):
            if not self.custom_temp_dir and self.temp_obj:
                self.temp_obj.cleanup()
                logger.info("Cleaned up temporary directory")

    # Process segments using the appropriate temporary directory
    with TempDirManager(temp_dir) as working_dir:
        segment_files = []
        failed_segments = []

        # Process each segment
        for i, segment in enumerate(segments):
            success, segment_file = process_segment(segment, i, video_files, working_dir,
                                                output_width, output_height)
            if success and segment_file:
                segment_files.append(segment_file)
            else:
                failed_segments.append(i)
                logger.error(f"Failed to process segment {i+1} after all retries")

        if failed_segments:
            logger.warning(f"Warning: {len(failed_segments)} segments failed to process: {failed_segments}")
            if len(failed_segments) == len(segments):
                raise ValueError("All segments failed to process")

        # Create file list for concatenation
        concat_file = os.path.join(working_dir, 'concat.txt')
        with open(concat_file, 'w') as f:
            for segment_file in segment_files:
                if os.path.exists(segment_file):  # Only include successfully created segments
                    f.write(f"file '{segment_file}'\n")

        # Create temporary video without audio, using re-encode instead of copy
        temp_video = os.path.join(working_dir, 'temp_final.mp4')
        concat_cmd = [
            'ffmpeg', '-y',
            '-v', 'warning',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-video_track_timescale', '30000',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            '-color_range', '1',
            '-colorspace', 'bt709',
            '-color_primaries', 'bt709',
            '-color_trc', 'bt709',
            temp_video
        ]

        run_ffmpeg_command(concat_cmd, concat_file, temp_video, 999999)

        # Add custom audio track if provided
        if audio_file:
            logger.info("Adding custom audio track...")

            try:
                audio_duration = get_audio_duration(audio_file)
                logger.info(f"Audio duration: {audio_duration} seconds")

                final_cmd = [
                    'ffmpeg', '-y',
                    '-v', 'warning',
                    '-i', temp_video,
                    '-i', audio_file,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-shortest',
                    output_file
                ]

                run_ffmpeg_command(final_cmd, temp_video, output_file, 999999)

            except Exception as e:
                logger.error(f"Error processing audio file: {e}")
                logger.info("Falling back to video without audio")
                os.replace(temp_video, output_file)
        else:
            os.replace(temp_video, output_file)

        logger.info(f"Video creation complete: {output_file}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Create edited video from segments')
    parser.add_argument('segments_file', help='Path to JSON file containing segment information')
    parser.add_argument('video_folder', help='Path to folder or comma-separated list of folders containing source videos')
    parser.add_argument('output_file', help='Path where the final video should be saved')
    parser.add_argument('--width', type=int, default=1920, help='Output video width (default: 1920)')
    parser.add_argument('--height', type=int, default=1080, help='Output video height (default: 1080)')
    parser.add_argument('--audio', help='Path to audio file to use as soundtrack')
    parser.add_argument('--extensions', default='mp4,mov,mkv,avi',
                      help='Comma-separated list of video file extensions to include (default: mp4,mov,mkv,avi)')
    parser.add_argument('--temp-dir', help='Optional custom temporary directory path')

    args = parser.parse_args()

    create_edited_video(
        args.segments_file,
        args.video_folder,
        args.output_file,
        args.width,
        args.height,
        args.audio,
        args.extensions,
        args.temp_dir
    )