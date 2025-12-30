import random
import os
from midiutil import MIDIFile

# === 1. 이미지 스펙 상수 정의 ===
TICKS_PER_BEAT = 1000  # 틱/비트 (Spec)
TEMPO = 60  # 60 BPM (Spec)
TIME_SIGNATURE = (4, 4)  # 4/4 박자

# === 2. 악기 및 채널 설정 (핵심 수정) ===
# 트랙 번호 : (MIDI Program 번호, MIDI Channel 번호)
# Channel 0과 1로 확실히 분리
INSTRUMENTS_CONFIG = {
    0: {'program': 0, 'channel': 0, 'name': 'Piano'},  # Track 0: Piano (Ch 0)
    1: {'program': 40, 'channel': 1, 'name': 'Violin'}  # Track 1: Violin (Ch 1)
}

# === 3. 음악 이론 데이터 ===
CHORD_PROGRESSIONS = [
    ['C', 'G', 'Am', 'F'],
    ['Am', 'F', 'C', 'G'],
    ['F', 'C', 'Dm', 'G'],
    ['C', 'Em', 'F', 'G']
]

CHORD_MAP = {
    'C': [60, 64, 67], 'G': [55, 59, 62],
    'Am': [57, 60, 64], 'Em': [52, 55, 59],
    'F': [53, 57, 60], 'Dm': [50, 53, 57]
}

SCALE = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79]


def create_corrected_midi(file_index, output_folder="Source"):
    # 2개 트랙 생성
    midi = MIDIFile(2, ticks_per_quarternote=TICKS_PER_BEAT)

    # 공통 설정 (템포, 박자, 악기)
    for track_idx in range(2):
        config = INSTRUMENTS_CONFIG[track_idx]
        channel = config['channel']
        program = config['program']

        midi.addTempo(track_idx, 0, TEMPO)
        # 박자 정보 추가 (Time Signature: 4/4, 24 clocks, 8 32nd notes)
        midi.addTimeSignature(track_idx, 0, 4, 2, 24)
        midi.addTrackName(track_idx, 0, config['name'])
        midi.addProgramChange(track_idx, channel, 0, program)

    # 랜덤 코드 진행
    progression = random.choice(CHORD_PROGRESSIONS)
    total_bars = 8
    time = 0

    for bar in range(total_bars):
        chord_name = progression[bar % 4]
        chord_notes = CHORD_MAP[chord_name]

        # --- Track 0: Piano (Channel 0) ---
        p_channel = INSTRUMENTS_CONFIG[0]['channel']

        # 피아노 아르페지오 (8분음표 단위)
        for _ in range(2):
            for i, note_idx in enumerate([0, 1, 2, 1]):
                velocity = random.randint(55, 75)
                pitch = chord_notes[note_idx]
                start_time = time + (i * 0.5)
                # **중요: p_channel 사용**
                midi.addNote(0, p_channel, pitch, start_time, 0.5, velocity)
            time += 2

            # --- Track 1: Violin (Channel 1) ---
        v_channel = INSTRUMENTS_CONFIG[1]['channel']

        # 현재 마디 시작점으로 바이올린 포인터 이동
        current_bar_start = time - 4
        v_time = current_bar_start
        remaining_duration = 4.0

        while remaining_duration > 0:
            choices = [1.0, 2.0, 4.0]
            valid_durs = [d for d in choices if d <= remaining_duration]
            if not valid_durs:
                dur = remaining_duration
            else:
                dur = random.choice(valid_durs)

            if random.random() < 0.7:
                note = random.choice(chord_notes) + 12
            else:
                note = random.choice(SCALE)

            # **중요: v_channel 사용**
            midi.addNote(1, v_channel, note, v_time, dur, random.randint(85, 105))
            v_time += dur
            remaining_duration -= dur

    # 파일 저장
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    filename = f"{output_folder}/data_{file_index}.mid"
    with open(filename, "wb") as output_file:
        midi.writeFile(output_file)


# === 실행부 ===
if __name__ == "__main__":
    # 사용자가 원하는 파일 수 입력 (이미지상의 목표는 7823개)
    try:
        count = int(input("생성할 파일 개수를 입력하세요 (예: 10): "))
    except:
        count = 10

    print(f"총 {count}개의 파일 생성을 시작합니다...")
    print(f"Spec: 60 BPM, 1000 Ticks/Beat, Piano+Violin")

    for i in range(1, count + 1):
        create_corrected_midi(i)

    print("모든 파일 생성이 완료되었습니다.")