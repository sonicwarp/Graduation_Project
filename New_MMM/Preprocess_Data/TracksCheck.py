import os
import glob
from mido import MidiFile

# MIDI program 번호 → 악기 이름
INSTRUMENT_NAMES = {
    0: "Acoustic Grand Piano",
    1: "Bright Acoustic Piano",
    2: "Electric Grand Piano",
    3: "Honky-tonk Piano",
    4: "Electric Piano 1",
    5: "Electric Piano 2",
    6: "Harpsichord",
    7: "Clavinet",
    24: "Acoustic Guitar (nylon)",
    25: "Acoustic Guitar (steel)",
    26: "Electric Guitar (jazz)",
    27: "Electric Guitar (clean)",
    28: "Electric Guitar (muted)",
    29: "Overdriven Guitar",
    30: "Distortion Guitar",
    31: "Guitar Harmonics",
    32: "Acoustic Bass",
    33: "Electric Bass (finger)",
    34: "Electric Bass (pick)",
    35: "Fretless Bass",
    40: "Violin",
    41: "Viola",
    42: "Cello",
    43: "Contrabass",
    44: "Tremolo Strings",
    45: "Pizzicato Strings",
    46: "Orchestral Harp",
    47: "Timpani",
    48: "String Ensemble 1",
    49: "String Ensemble 2",
    56: "Trumpet",
    57: "Trombone",
    58: "Tuba",
    59: "Muted Trumpet",
    60: "French Horn",
    61: "Brass Section",
    64: "Soprano Sax",
    65: "Alto Sax",
    66: "Tenor Sax",
    67: "Baritone Sax",
    68: "Oboe",
    69: "English Horn",
    70: "Bassoon",
    71: "Clarinet",
    72: "Piccolo",
    73: "Flute",
    74: "Recorder",
}


def get_instrument_name(program):
    """MIDI program 번호 → 악기 이름"""
    return INSTRUMENT_NAMES.get(program, f"Program {program}")


def analyze_midi_by_channel(midi_path):
    """MIDI 파일을 채널 기반으로 분석"""
    mid = MidiFile(midi_path)

    # 채널별 정보 수집
    channels = {}

    # 템포, 박자 정보
    tempo = None
    time_signature = None
    ticks_per_beat = mid.ticks_per_beat

    for track in mid.tracks:
        for msg in track:
            # 메타 메시지 (템포, 박자)
            if msg.is_meta:
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                elif msg.type == 'time_signature':
                    time_signature = f"{msg.numerator}/{msg.denominator}"

            # 채널 메시지 (음표, 악기)
            if hasattr(msg, 'channel'):
                ch = msg.channel
                if ch not in channels:
                    channels[ch] = {'notes': 0, 'program': None}

                if msg.type == 'note_on' and msg.velocity > 0:
                    channels[ch]['notes'] += 1
                elif msg.type == 'program_change':
                    channels[ch]['program'] = msg.program

    # 음표가 있는 채널만 반환
    channel_result = {}
    for ch, info in channels.items():
        if info['notes'] > 0:
            channel_result[ch] = {
                'program': info['program'],
                'instrument': get_instrument_name(info['program']) if info['program'] is not None else "Unknown",
                'notes': info['notes']
            }

    # BPM 계산
    bpm = 60_000_000 / tempo if tempo else None

    return {
        'channels': channel_result,
        'tempo': tempo,
        'bpm': bpm,
        'time_signature': time_signature,
        'ticks_per_beat': ticks_per_beat
    }


def analyze_all_midi_files(midi_folder):
    """폴더 내 모든 MIDI 파일 분석"""

    # MIDI 파일 찾기
    midi_files = sorted(glob.glob(os.path.join(midi_folder, "*.mid")))
    if not midi_files:
        midi_files = sorted(glob.glob(os.path.join(midi_folder, "*.midi")))

    print(f"총 {len(midi_files)}개 MIDI 파일 발견\n")

    # 통계
    all_results = []
    instrument_counter = {}
    combination_counter = {}
    tempo_counter = {}
    time_sig_counter = {}

    for midi_path in midi_files:
        filename = os.path.basename(midi_path)

        try:
            analysis = analyze_midi_by_channel(midi_path)
            channels = analysis['channels']
            bpm = analysis['bpm']
            time_sig = analysis['time_signature']

            # 악기 조합 (정렬된 튜플로)
            instruments = tuple(sorted([info['instrument'] for info in channels.values()]))
            combination_counter[instruments] = combination_counter.get(instruments, 0) + 1

            # 개별 악기 카운트
            for info in channels.values():
                inst = info['instrument']
                instrument_counter[inst] = instrument_counter.get(inst, 0) + 1

            # 템포 카운트
            bpm_rounded = round(bpm) if bpm else "Unknown"
            tempo_counter[bpm_rounded] = tempo_counter.get(bpm_rounded, 0) + 1

            # 박자 카운트
            time_sig_counter[time_sig] = time_sig_counter.get(time_sig, 0) + 1

            all_results.append({
                'filename': filename,
                'channels': channels,
                'instruments': instruments,
                'bpm': bpm,
                'time_signature': time_sig,
                'ticks_per_beat': analysis['ticks_per_beat']
            })

        except Exception as e:
            print(f"에러 - {filename}: {e}")

    return all_results, instrument_counter, combination_counter, tempo_counter, time_sig_counter


def print_summary(all_results, instrument_counter, combination_counter, tempo_counter, time_sig_counter):
    """결과 요약 출력"""

    print("=" * 60)
    print("전체 요약")
    print("=" * 60)

    print(f"\n총 파일 수: {len(all_results)}")

    print("\n--- 악기별 등장 횟수 ---")
    for inst, count in sorted(instrument_counter.items(), key=lambda x: -x[1]):
        print(f"  {inst}: {count}회")

    print("\n--- 악기 조합별 파일 수 ---")
    for combo, count in sorted(combination_counter.items(), key=lambda x: -x[1]):
        combo_str = " + ".join(combo) if combo else "(없음)"
        print(f"  {combo_str}: {count}개")

    print("\n--- 템포(BPM)별 파일 수 ---")
    for bpm, count in sorted(tempo_counter.items(), key=lambda x: -x[1]):
        print(f"  {bpm} BPM: {count}개")

    print("\n--- 박자별 파일 수 ---")
    for time_sig, count in sorted(time_sig_counter.items(), key=lambda x: -x[1]):
        print(f"  {time_sig}: {count}개")

    print("\n--- 샘플 파일 상세 (처음 10개) ---")
    for result in all_results[:10]:
        print(f"\n{result['filename']} (BPM: {result['bpm']}, 박자: {result['time_signature']}):")
        for ch, info in sorted(result['channels'].items()):
            print(f"  채널 {ch}: {info['instrument']} ({info['notes']}개 음표)")


def find_piano_violin_files(all_results):
    """피아노 + 바이올린 조합 파일 찾기"""
    matched = []

    for result in all_results:
        instruments_lower = [inst.lower() for inst in result['instruments']]
        has_piano = any('piano' in inst for inst in instruments_lower)
        has_violin = any('violin' in inst for inst in instruments_lower)

        if has_piano and has_violin:
            matched.append(result)

    return matched


if __name__ == "__main__":
    # ⚠️ 이 경로를 네 MIDI 폴더로 수정해!
    #midi_folder = r"C:\Users\Admin\Desktop\Graduation\Sources"
    midi_folder = r"C:\Users\Admin\Desktop\PythonProject2\MMM_JSB\NewMusic\Source"
    print("MIDI 파일 분석 시작 (채널 기반)...\n")

    results, inst_counter, combo_counter, tempo_counter, time_sig_counter = analyze_all_midi_files(midi_folder)
    print_summary(results, inst_counter, combo_counter, tempo_counter, time_sig_counter)

    # 피아노 + 바이올린 파일 찾기
    print("\n" + "=" * 60)
    print("피아노 + 바이올린 조합 파일")
    print("=" * 60)

    matched = find_piano_violin_files(results)
    print(f"\n총 {len(matched)}개 파일")

    for m in matched[:5]:
        print(f"  - {m['filename']}")