#!/bin/bash

# Function to display help menu
display_help() {
    echo "Media Processing Pipeline"
    echo "Usage: $0 [options] input_directory output_directory"
    echo
    echo "Options:"
    echo "  --help                   Show this help message"
    echo "  -a, --audio-extensions    Audio file extensions to process (comma-separated)"
    echo "  -v, --video-extensions    Video file extensions to process (comma-separated)"
    echo "  -w, --width               Output video width (default: 1280)"
    echo "  -h, --height              Output video height (default: 720)"
    echo "  -d, --video-dirs          Comma-separated list of directories containing input video files"
    echo "  -t, --temp-dir            Directory for temporary files (default: system temp)"
    echo
    echo "Example:"
    echo "  $0 -a 'mp3,wav,m4a' -v 'mp4,avi,mov' -w 1920 -h 1080 -d './videos1,./videos2,./videos3' -t ./temp ./input_folder ./output_folder"
    echo
    echo "Note: Each processed file will create an output MP4 with the same base name"
    echo "      in the output directory (e.g., input.mp3 -> output/input.mp4)"
}

# Default values
width=1280
height=720
audio_extensions=""
video_extensions=""
video_dirs=""
temp_dir=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            display_help
            exit 0
            ;;
        -a|--audio-extensions)
            audio_extensions="$2"
            shift 2
            ;;
        -v|--video-extensions)
            video_extensions="$2"
            shift 2
            ;;
        -w|--width)
            width="$2"
            shift 2
            ;;
        -h|--height)
            height="$2"
            shift 2
            ;;
        -d|--video-dirs)
            video_dirs="$2"
            shift 2
            ;;
        -t|--temp-dir)
            temp_dir="$2"
            shift 2
            ;;
        -*)
            echo "Error: Unknown option $1"
            display_help
            exit 1
            ;;
        *)
            if [ -z "$input_dir" ]; then
                input_dir="$1"
            elif [ -z "$output_dir" ]; then
                output_dir="$1"
            else
                echo "Error: Unexpected argument '$1'"
                display_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Debug output
echo "Debug values:"
echo "audio_extensions: $audio_extensions"
echo "video_extensions: $video_extensions"
echo "width: $width"
echo "height: $height"
echo "video_dirs: $video_dirs"
echo "temp_dir: $temp_dir"
echo "input_dir: $input_dir"
echo "output_dir: $output_dir"

# Validate required arguments
if [ -z "$input_dir" ] || [ -z "$output_dir" ] || [ -z "$audio_extensions" ] || [ -z "$video_extensions" ] || [ -z "$video_dirs" ]; then
    echo "Error: Missing required arguments"
    echo "input_dir: $input_dir"
    echo "output_dir: $output_dir"
    echo "audio_extensions: $audio_extensions"
    echo "video_extensions: $video_extensions"
    echo "video_dirs: $video_dirs"
    display_help
    exit 1
fi

# Convert to absolute paths
input_dir=$(realpath "$input_dir")
output_dir=$(realpath "$output_dir")

# Convert and validate video directories
IFS=',' read -ra video_dir_array <<< "$video_dirs"
valid_video_dirs=""
for dir in "${video_dir_array[@]}"; do
    # Remove any whitespace
    dir=$(echo "$dir" | tr -d '[:space:]')
    if [ ! -d "$dir" ]; then
        echo "Warning: Video directory does not exist: $dir"
        continue
    fi
    abs_dir=$(realpath "$dir")
    if [ -z "$valid_video_dirs" ]; then
        valid_video_dirs="$abs_dir"
    else
        valid_video_dirs="$valid_video_dirs,$abs_dir"
    fi
done

if [ -z "$valid_video_dirs" ]; then
    echo "Error: No valid video directories found"
    exit 1
fi

echo "Valid video directories: $valid_video_dirs"

if [ ! -z "$temp_dir" ]; then
    temp_dir=$(realpath "$temp_dir")
    # Create temp directory if it doesn't exist
    mkdir -p "$temp_dir"
fi

# Create output directory if it doesn't exist
mkdir -p "$output_dir"

# Convert audio extensions string to array
IFS=',' read -ra audio_ext_array <<< "$audio_extensions"

# Find and display all matching files before processing
echo -e "\nDiscovering all audio files:"
echo "=============================="
declare -a all_files
for ext in "${audio_ext_array[@]}"; do
    # Remove any whitespace and add the dot prefix
    ext=$(echo "$ext" | tr -d '[:space:]')
    ext=".$ext"
    echo -e "\nFiles with extension: $ext"
    echo "-------------------------"
    while IFS= read -r -d '' file; do
        echo "$file"
        all_files+=("$file")
    done < <(find "$input_dir" -type f -name "*$ext" -print0)
done

# Display total count
echo -e "\nTotal files found: ${#all_files[@]}"
echo "=============================="
echo -e "Beginning processing...\n"

# Process each file in the array
for file in "${all_files[@]}"; do
    # Get absolute path
    abs_path=$(realpath "$file")

    # Extract filename without extension
    filename=$(basename "$file")
    basename="${filename%.*}"

    # Define output MP4 path
    output_mp4="$output_dir/${basename}.mp4"

    echo "Processing: $abs_path"
    echo "Output will be: $output_mp4"

    # Run audio analyzer
    if ! python3 audio_analyzer.py "$abs_path"; then
        echo "Error: Audio analysis failed for $abs_path"
        continue
    fi

    # Get the JSON file path (same location as input file)
    json_path="${abs_path%.*}.json"

    # Check if JSON file was created
    if [ ! -f "$json_path" ]; then
        echo "Error: JSON file not created for $abs_path"
        continue
    fi

    # Build video editor command with optional temp directory
    video_editor_cmd="python3 video_editor.py \"$json_path\" \"$valid_video_dirs\" \"$output_mp4\" --width \"$width\" --height \"$height\" --extensions \"$video_extensions\" --audio \"$abs_path\""
    if [ ! -z "$temp_dir" ]; then
        video_editor_cmd+=" --temp-dir \"$temp_dir\""
    fi

    echo "Running command: $video_editor_cmd"

    # Run video editor
    if ! eval "$video_editor_cmd"; then
        echo "Error: Video editing failed for $abs_path"
        continue
    fi

    echo "Successfully processed: $abs_path -> $output_mp4"
done

echo "Processing complete!"