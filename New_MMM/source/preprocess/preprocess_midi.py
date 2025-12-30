# MIDI 파일 전처리 (채널 기반)
# 피아노 + 바이올린 데이터셋용

import os
import glob
from mido import MidiFile

# 설정값
TICKS_PER_BEAT = 1000
BEATS_PER_BAR = 4
TICKS_PER_BAR = TICKS_PER_BEAT * BEATS_PER_BAR  # 4000

# 채널 → 악기 매핑
CHANNEL_TO_INSTRUMENT = {
    0: {"name": "Piano", "number": 0},
    3: {"name": "Violin", "number": 1},
}


def preprocess_midi_folder(midi_folder, train_ratio=0.8):
    """
    폴더 내 모든 MIDI 파일을 전처리

    Returns:
        songs_data_train: 학습용 데이터
        songs_data_valid: 검증용 데이터
    """

    # MIDI 파일 찾기
    midi_files = sorted(glob.glob(os.path.join(midi_folder, "*.mid")))
    if not midi_files:
        midi_files = sorted(glob.glob(os.path.join(midi_folder, "*.midi")))

    print(f"총 {len(midi_files)}개 MIDI 파일 발견")

    # 전처리
    songs_data = []
    for midi_path in midi_files:
        song_data = preprocess_midi_file(midi_path)
        if song_data is not None:
            songs_data.append(song_data)

    print(f"전처리 완료: {len(songs_data)}개 곡")

    # Train/Valid 분할
    split_index = int(len(songs_data) * train_ratio)
    songs_data_train = songs_data[:split_index]
    songs_data_valid = songs_data[split_index:]

    print(f"학습용: {len(songs_data_train)}개")
    print(f"검증용: {len(songs_data_valid)}개")

    return songs_data_train, songs_data_valid


def preprocess_midi_file(midi_path):
    """
    단일 MIDI 파일을 JSON 형식으로 변환

    Returns:
        song_data = {
            "title": "파일명",
            "tracks": [
                {"name": "Piano", "number": 0, "bars": [...]},
                {"name": "Violin", "number": 1, "bars": [...]}
            ]
        }
    """

    try:
        mid = MidiFile(midi_path)
    except Exception as e:
        print(f"에러 - {midi_path}: {e}")
        return None

    filename = os.path.basename(midi_path)

    # 채널별 음표 수집
    channel_notes = {}  # {channel: [(pitch, start_tick, end_tick), ...]}

    for track in mid.tracks:
        current_tick = 0
        note_on_times = {}  # {(channel, pitch): start_tick}

        for msg in track:
            current_tick += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                key = (msg.channel, msg.note)
                note_on_times[key] = current_tick

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in note_on_times:
                    start_tick = note_on_times[key]
                    end_tick = current_tick

                    channel = msg.channel
                    if channel not in channel_notes:
                        channel_notes[channel] = []

                    channel_notes[channel].append({
                        'pitch': msg.note,
                        'start': start_tick,
                        'end': end_tick
                    })

                    del note_on_times[key]

    # 우리가 원하는 채널만 필터링 (피아노: 0, 바이올린: 3)
    if 0 not in channel_notes or 3 not in channel_notes:
        print(f"스킵 - {filename}: 피아노 또는 바이올린 채널 없음")
        return None

    # 곡의 총 길이 (틱)
    max_tick = 0
    for notes in channel_notes.values():
        for note in notes:
            max_tick = max(max_tick, note['end'])

    # 마디 수 계산
    num_bars = (max_tick // TICKS_PER_BAR) + 1

    # 트랙별로 변환
    tracks = []
    for channel, instrument_info in CHANNEL_TO_INSTRUMENT.items():
        notes = channel_notes.get(channel, [])

        track_data = {
            "name": instrument_info["name"],
            "number": instrument_info["number"],
            "bars": []
        }

        # 마디별로 음표 분류
        for bar_index in range(num_bars):
            bar_start_tick = bar_index * TICKS_PER_BAR
            bar_end_tick = (bar_index + 1) * TICKS_PER_BAR

            bar_data = notes_to_bar_data(notes, bar_start_tick, bar_end_tick)
            track_data["bars"].append(bar_data)

        tracks.append(track_data)

    song_data = {
        "title": filename,
        "tracks": tracks
    }

    return song_data


def notes_to_bar_data(notes, bar_start_tick, bar_end_tick):
    """
    특정 마디에 속하는 음표들을 이벤트 형식으로 변환

    Returns:
        bar_data = {
            "events": [
                {"type": "NOTE_ON", "pitch": 60},
                {"type": "TIME_DELTA", "delta": 4.0},
                {"type": "NOTE_OFF", "pitch": 60},
                ...
            ]
        }
    """

    # 이 마디에 속하는 음표 찾기
    bar_notes = []
    for note in notes:
        # 음표가 이 마디와 겹치는지 확인
        if note['start'] < bar_end_tick and note['end'] > bar_start_tick:
            bar_notes.append(note)

    # 이벤트로 변환 (NOTE_ON, NOTE_OFF)
    events = []
    for note in bar_notes:
        # 마디 내 상대 위치로 변환 (틱 → 16분음표 단위)
        # 1비트 = 1000틱, 16분음표 = 0.25비트 = 250틱
        start_in_bar = max(0, note['start'] - bar_start_tick)
        end_in_bar = min(TICKS_PER_BAR, note['end'] - bar_start_tick)

        # 틱을 16분음표 단위로 변환 (250틱 = 1)
        start_16th = start_in_bar / 250
        end_16th = end_in_bar / 250

        events.append(("NOTE_ON", note['pitch'], start_16th))
        events.append(("NOTE_OFF", note['pitch'], end_16th))

    # 시간순 정렬 후 이벤트 데이터로 변환
    events_data = events_to_events_data(events)

    return {"events": events_data}


def events_to_events_data(events):
    """
    (type, pitch, time) 튜플 리스트를 이벤트 딕셔너리 리스트로 변환
    TIME_DELTA 추가
    """

    if not events:
        return []

    # 시간순 정렬
    events = sorted(events, key=lambda e: e[2])

    events_data = []
    for i, (event_type, pitch, time) in enumerate(events):
        # 첫 이벤트 전에 시간이 있으면 TIME_DELTA 추가
        if i == 0 and time > 0:
            events_data.append({
                "type": "TIME_DELTA",
                "delta": time
            })

        # 이벤트 추가
        events_data.append({
            "type": event_type,
            "pitch": pitch
        })

        # 다음 이벤트와의 시간 차이
        if i < len(events) - 1:
            next_time = events[i + 1][2]
            delta = next_time - time
            if delta > 0:
                events_data.append({
                    "type": "TIME_DELTA",
                    "delta": delta
                })

    return events_data


# 테스트용
if __name__ == "__main__":
    import json

    # ⚠️ 경로 수정 필요
    midi_folder = r"C:\Users\Admin\Desktop\Graduation\Sources"

    # 전체 전처리
    # songs_train, songs_valid = preprocess_midi_folder(midi_folder)

    # 단일 파일 테스트
    # test_file = os.path.join(midi_folder, "Mono-Melodies-0000.mid")
    # song_data = preprocess_midi_file(test_file)
    #
    # if song_data:
    #     print("\n=== 전처리 결과 ===")
    #     print(f"제목: {song_data['title']}")
    #     print(f"트랙 수: {len(song_data['tracks'])}")
    #
    #     for track in song_data['tracks']:
    #         print(f"\n[{track['name']}] - {len(track['bars'])}마디")
    #
    #         # 첫 2마디만 출력
    #         for bar_idx, bar in enumerate(track['bars'][:2]):
    #             print(f"  마디 {bar_idx + 1}: {len(bar['events'])}개 이벤트")
    #             for event in bar['events'][:5]:
    #                 print(f"    {event}")
    #             if len(bar['events']) > 5:
    #                 print(f"    ... ({len(bar['events']) - 5}개 더)")

    # 전체 전처리 실행
    songs_train, songs_valid = preprocess_midi_folder(midi_folder)
    print(f"완료! 학습: {len(songs_train)}개, 검증: {len(songs_valid)}개")