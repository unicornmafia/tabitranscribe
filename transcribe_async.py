#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Speech API sample application using the REST API for async
batch processing.

Example usage:
    python transcribe_async.py resources/audio.raw
    python transcribe_async.py gs://cloud-samples-tests/speech/vr.flac
"""

import argparse
import io
import time

# [START def_transcribe_file]
def transcribe_file(speech_file):
    """Transcribe the given audio file asynchronously."""
    from google.cloud import speech
    from google.cloud.speech import enums
    from google.cloud.speech import types
    client = speech.SpeechClient()

    # [START migration_async_request]
    with io.open(speech_file, 'rb') as audio_file:
        content = audio_file.read()

    audio = types.RecognitionAudio(content=content)
    config = types.RecognitionConfig(
        #encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        enable_word_time_offset=True,
        encoding=enums.RecognitionConfig.AudioEncoding.FLAC,
        #sample_rate_hertz=32000,
        language_code='en-US')

    # [START migration_async_response]
    operation = client.long_running_recognize(config, audio)
    # [END migration_async_request]

    print('Waiting for operation to complete...')
    response = operation.result(timeout=90)

    # Print the first alternative of all the consecutive results.
    for result in response.results:
        print('Transcript: {}'.format(result.alternatives[0].transcript))
        print('Confidence: {}'.format(result.alternatives[0].confidence))
    # [END migration_async_response]
# [END def_transcribe_file]


def format_time_string(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    outstring = '%02d:%02d:%02d' % (h, m, s)
    return outstring


class Word(object):
    def __init__(self, word, start_time_s, start_time_ms, end_time_s, end_time_ms, gap):
        self.start_time_s = start_time_s
        self.start_time_ms = start_time_ms
        self.end_time_s = end_time_s
        self.end_time_ms = end_time_ms
        self.gap = gap
        self.word = word

class Phrase(object):
    def __init__(self, text, start_time_s, start_time_ms, end_time_s, end_time_ms):
        self.start_time_s = start_time_s
        self.start_time_ms = start_time_ms
        self.end_time_s = end_time_s
        self.end_time_ms = end_time_ms
        self.text = text


def concat_word_list(results):
    word_list = []
    for result in results:
        words = result.alternatives[0].words
        last_end = None
        for word in words:
            start_time_s = word.start_time.seconds
            start_time_ms = word.start_time.nanos * 10**-6
            end_time_s = word.end_time.seconds
            end_time_ms = word.end_time.nanos * 10**-6
            start_time = start_time_s + start_time_ms*10**-3
            end_time = end_time_s + end_time_ms*10**-3
            if last_end is None:
                gap = 0
            else:
                gap = start_time - last_end
            word = Word(word.word, start_time_s, start_time_ms, end_time_s, end_time_ms, gap)
            word_list.append(word)
            last_end = end_time
    return word_list

def make_phrase_list(words):
    phrases = []
    gap_threshold = 1.0
    current_phrase = ""
    start_time_s = 0
    start_time_ms = 0
    num_words = 0
    for word in words:
        if not num_words:
            start_time_s = word.start_time_s
            start_time_ms = word.start_time_ms
        if word.gap > gap_threshold or num_words > 10:
            if current_phrase:
                end_time_s = word.end_time_s
                end_time_ms = word.end_time_ms
                phrases.append(Phrase(current_phrase.strip(), start_time_s, start_time_ms, end_time_s, end_time_ms))
                current_phrase = ""
                num_words = 0
        else:
            current_phrase += word.word + " "
            num_words += 1
    return phrases


def write_srt_file(srt_file, phrases):
    counter = 0
    for phrase in phrases:
        srt_file.write(str(counter) + "\n")
        start_time_code = format_time_string(phrase.start_time_s) + ",%03d" % (phrase.start_time_ms)

        end_time_code = format_time_string(phrase.end_time_s) + ",%03d" % (phrase.end_time_ms)
        time_code = start_time_code + " --> " + end_time_code
        srt_file.write(time_code + "\n")
        srt_file.write(phrase.text + "\n\n")

        counter += 1


# [START def_transcribe_gcs]
def transcribe_gcs(gcs_uri):
    """Asynchronously transcribes the audio file specified by the gcs_uri."""
    from google.cloud import speech
    from google.cloud.speech import enums
    from google.cloud.speech import types
    client = speech.SpeechClient()

    audio = types.RecognitionAudio(uri=gcs_uri)
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.FLAC,
        enable_word_time_offsets=True,
        #sample_rate_hertz=32000,
        language_code='en-US')

    operation_start_time = time.time()
    operation = client.long_running_recognize(config, audio)


    print('Waiting for operation to complete...')
    response = operation.result(timeout=None)
    operation_end_time = time.time()
    operation_elapsed_time = operation_end_time - operation_start_time
    operation_time_string = format_time_string(operation_elapsed_time)

    last_result_index = len(response.results)-1
    last_word_index = len(response.results[last_result_index].alternatives[0].words)-1
    audio_duration = response.results[last_result_index].alternatives[0].words[last_word_index].end_time.seconds
    audio_duration_string = format_time_string(audio_duration)

    counter = 1
    srt_file_name = gcs_uri[gcs_uri.rfind("/")+1:gcs_uri.rfind(".mp4-audio.")]+".srt"
    srt_file = open(srt_file_name, "w")

    srt_file_name2 = gcs_uri[gcs_uri.rfind("/") + 1:gcs_uri.rfind(".mp4-audio.")] + "2.srt"
    srt_file2 = open(srt_file_name2, "w")

    transcription_file_name = gcs_uri[gcs_uri.rfind("/") + 1:gcs_uri.rfind("-audio.")] + "-transcription.txt"
    transcription_file = open(transcription_file_name, "w")

    word_list = concat_word_list(response.results)
    phrase_list = make_phrase_list(word_list)
    write_srt_file(srt_file2, phrase_list)

    # Print the first alternative of all the consecutive results.
    for result in response.results:
        transcript = result.alternatives[0].transcript.strip()
        seconds = result.alternatives[0].words[0].start_time.seconds
        last_word_index = len(result.alternatives[0].words)-1
        end_seconds = result.alternatives[0].words[last_word_index].end_time.seconds
        outstring = format_time_string(seconds) + " - " +transcript
        print(outstring + "\n")
        transcription_file.write(outstring + "\n\n")

        # now write to srt file
        srt_file.write(str(counter)+"\n")
        start_time_code = format_time_string(seconds) + ",000"

        end_time_code = format_time_string(end_seconds) + ",000"
        time_code = start_time_code + " --> " + end_time_code
        srt_file.write(time_code + "\n")
        srt_file.write(transcript + "\n\n")
        counter += 1
        #print('Confidence: {}'.format(result.alternatives[0].confidence))
    srt_file.close()
    srt_file2.close()
    transcription_file.close()
    print("\n------------------------------------------------")
    print("Audio file length: " + audio_duration_string)
    print("Transcribe operation running time: " + operation_time_string)
    print("------------------------------------------------")

# [END def_transcribe_gcs]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'path', help='File or GCS path for audio file to be recognized')
    args = parser.parse_args()
    if args.path.startswith('gs://'):
        transcribe_gcs(args.path)
    else:
        transcribe_file(args.path)
