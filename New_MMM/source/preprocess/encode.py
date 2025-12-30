# Copyright 2021 Tristan Behrens.
# Modified for track_fill functionality.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3

import itertools
import numpy as np
import random
import json
import copy


def encode_songs_data(songs_data, transpositions, permute, window_size_bars, hop_length_bars, density_bins, bar_fill,
                      track_fill=False, fill_track_number=1):
    """
    곡 데이터들을 토큰 시퀀스로 변환

    Args:
        songs_data: 곡 데이터 리스트
        transpositions: 조옮김 리스트 (예: [-2, -1, 0, 1, 2])
        permute: 트랙 순서 섞을지 여부
        window_size_bars: 윈도우 크기 (마디 단위)
        hop_length_bars: 홉 길이 (마디 단위)
        density_bins: 밀도 구간
        bar_fill: 기존 bar_fill 모드
        track_fill: 새로운 track_fill 모드 (트랙 전체를 FILL_IN으로)
        fill_track_number: 비울 트랙 번호 (기본값 1 = 바이올린)
    """

    # This will be returned.
    token_sequences = []

    # Go through all songs.
    for song_data in songs_data:
        token_sequences += encode_song_data(
            song_data, transpositions, permute,
            window_size_bars, hop_length_bars, density_bins,
            bar_fill, track_fill, fill_track_number
        )

    # Done.
    return token_sequences


def encode_song_data(song_data, transpositions, permute, window_size_bars, hop_length_bars, density_bins, bar_fill,
                     track_fill=False, fill_track_number=1):
    """
    단일 곡 데이터를 토큰 시퀀스로 변환
    """

    # This will be returned.
    token_sequences = []

    # Count the bars.
    bars = get_bars_number(song_data)

    # For iterating over the bars.
    bar_indices = get_bar_indices(bars, window_size_bars, hop_length_bars)

    # Go through all combinations.
    count = 0
    for (bar_start_index, bar_end_index), transposition in itertools.product(bar_indices, transpositions):

        # ⭐ 중요: deep copy로 원본 데이터 보호
        song_data_copy = copy.deepcopy(song_data)

        # Start empty
        token_sequence = []

        # =====================
        # 기존 bar_fill 로직
        # =====================
        bar_data_fill = None
        if bar_fill:
            track_data = random.choice(song_data_copy["tracks"])
            bar_data = random.choice(track_data["bars"][bar_start_index:bar_end_index])
            bar_data_fill = {"events": bar_data["events"]}
            bar_data["events"] = "bar_fill"

        # =====================
        # 새로운 track_fill 로직
        # =====================
        fill_bars_backup = []
        if track_fill:
            # 1. 비울 트랙 찾기 (fill_track_number와 일치하는 트랙)
            fill_track_index = None
            for i, track in enumerate(song_data_copy["tracks"]):
                if track["number"] == fill_track_number:
                    fill_track_index = i
                    break

            # 2. 해당 트랙의 마디들을 백업하고 비우기
            if fill_track_index is not None:
                fill_track = song_data_copy["tracks"][fill_track_index]
                for bar in fill_track["bars"][bar_start_index:bar_end_index]:
                    # 백업 (정답으로 사용)
                    fill_bars_backup.append({"events": bar["events"]})
                    # 비우기 (FILL_IN이 될 것)
                    bar["events"] = "bar_fill"

        # Start with the tokens.
        token_sequence += ["PIECE_START"]

        # Get the indices. Permute if necessary.
        track_data_indices = list(range(len(song_data_copy["tracks"])))
        if permute:
            random.shuffle(track_data_indices)

        # Encode the tracks.
        for track_data_index in track_data_indices:
            track_data = song_data_copy["tracks"][track_data_index]

            # Encode the track. Insert density tokens. Also transpose.
            encoded_track_data = encode_track_data(track_data, density_bins, bar_start_index, bar_end_index,
                                                   transposition)
            token_sequence += encoded_track_data

        # =====================
        # 기존 bar_fill 정답 토큰
        # =====================
        if bar_fill and bar_data_fill is not None:
            token_sequence += encode_bar_data(bar_data_fill, transposition, bar_fill=True)

        # =====================
        # 새로운 track_fill 정답 토큰
        # =====================
        if track_fill and len(fill_bars_backup) > 0:
            token_sequence += ["FILL_START"]
            for bar_backup in fill_bars_backup:
                # 각 마디의 음표들을 토큰으로 변환
                if bar_backup["events"] != "bar_fill":
                    for event_data in bar_backup["events"]:
                        token = encode_event_data(event_data, transposition)
                        if token is not None:
                            token_sequence += [token]
            token_sequence += ["FILL_END"]

        token_sequences += [token_sequence]
        count += 1

    # Done
    return token_sequences


def encode_track_data(track_data, density_bins, bar_start_index, bar_end_index, transposition):
    tokens = []

    tokens += ["TRACK_START"]

    # Set instrument.
    number = track_data["number"]

    # Set the instrument if it is a harmonic one.
    if not track_data.get("drums", False):
        tokens += [f"INST={number}"]

    # Set the instrument if it is drums. Also do not transpose drums.
    else:
        tokens += ["INST=DRUMS"]
        transposition = 0

    # Count note on events.
    note_on_events = 0
    for bar_data in track_data["bars"][bar_start_index:bar_end_index]:
        if bar_data["events"] == "bar_fill":
            continue
        for event_data in bar_data["events"]:
            if event_data["type"] == "NOTE_ON":
                note_on_events += 1

    # Determine density.
    density = np.digitize(note_on_events, density_bins)
    tokens += [f"DENSITY={density}"]

    # Encode the bars.
    for bar_data in track_data["bars"][bar_start_index:bar_end_index]:
        tokens += encode_bar_data(bar_data, transposition)

    tokens += ["TRACK_END"]

    return tokens


def encode_bar_data(bar_data, transposition, bar_fill=False):
    tokens = []

    if not bar_fill:
        tokens += ["BAR_START"]
    else:
        tokens += ["FILL_START"]

    if bar_data["events"] == "bar_fill":
        tokens += ["FILL_IN"]
    else:
        for event_data in bar_data["events"]:
            token = encode_event_data(event_data, transposition)
            if token is not None:
                tokens += [token]

    if not bar_fill:
        tokens += ["BAR_END"]
    else:
        tokens += ["FILL_END"]

    return tokens


def encode_event_data(event_data, transposition):
    if event_data["type"] == "NOTE_ON":
        return event_data["type"] + "=" + str(event_data["pitch"] + transposition)
    elif event_data["type"] == "NOTE_OFF":
        return event_data["type"] + "=" + str(event_data["pitch"] + transposition)
    elif event_data["type"] == "TIME_DELTA":
        return event_data["type"] + "=" + str(event_data["delta"])
    else:
        return None


def get_density_bins(songs_data, window_size_bars, hop_length_bars, bins):
    # Go through all songs and count the note on events for each window.\
    distribution = []
    for song_data in songs_data:
        # Count the bars.
        bars = get_bars_number(song_data)

        # Iterate over over the tracks and the bars.
        bar_indices = get_bar_indices(bars, window_size_bars, hop_length_bars)
        for track_data in song_data["tracks"]:
            for bar_start_index, bar_end_index in bar_indices:

                # Go through the bars and count notes.
                count = 0
                for bar in track_data["bars"][bar_start_index:bar_end_index]:
                    if bar["events"] == "bar_fill":
                        continue
                    count += len([event for event in bar["events"] if event["type"] == "NOTE_ON"])

                # Do not count empty tracks.
                if count != 0:
                    distribution += [count]

    # Compute the quantiles, which will become the density bins.
    quantiles = []
    for i in range(100 // bins, 100, 100 // bins):
        quantile = np.percentile(distribution, i)
        quantiles += [quantile]
    return quantiles


def get_density_bins_from_json_files(json_paths, window_size_bars, hop_length_bars, bins):
    # Go through all songs and count the note on events for each window.\
    distribution = []
    for json_path in json_paths:

        # Open the file and get the data.
        song_data = json.load(open(json_path, "r"))

        # Count the bars.
        bars = get_bars_number(song_data)

        # Iterate over over the tracks and the bars.
        bar_indices = get_bar_indices(bars, window_size_bars, hop_length_bars)
        for track_data in song_data["tracks"]:
            for bar_start_index, bar_end_index in bar_indices:

                # Go through the bars and count notes.
                count = 0
                for bar in track_data["bars"][bar_start_index:bar_end_index]:
                    if bar["events"] == "bar_fill":
                        continue
                    count += len([event for event in bar["events"] if event["type"] == "NOTE_ON"])

                # Do not count empty tracks.
                if count != 0:
                    distribution += [count]

    # Compute the quantiles, which will become the density bins.
    quantiles = []
    for i in range(100 // bins, 100, 100 // bins):
        quantile = np.percentile(distribution, i)
        quantiles += [quantile]
    return quantiles


def get_bars_number(song_data):
    bars = [len(track_data["bars"]) for track_data in song_data["tracks"]]
    bars = max(bars)
    return bars


def get_bar_indices(bars, window_size_bars, hop_length_bars):
    return list(zip(range(0, bars, hop_length_bars), range(window_size_bars, bars, hop_length_bars)))