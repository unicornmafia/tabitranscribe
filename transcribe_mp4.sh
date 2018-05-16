#!/bin/bash
set -x

# transcode to flac
ffmpeg -y -i $1 -ac 1 -c:a flac $1-audio.flac
gsutil cp $1-audio.flac gs://marshcomputedata
python transcribe_async.py gs://marshcomputedata/$1-audio.flac
