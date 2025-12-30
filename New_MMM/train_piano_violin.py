# Train script for Piano + Violin track fill model
# 피아노를 입력으로, 바이올린을 생성하도록 학습

import os
import sys

# source 폴더의 모듈들 import
from source import mmmtrainerconfig
from source import mmmtrainer
from source.preprocess.encode import encode_songs_data, get_density_bins
from source.preprocess.preprocess_midi import preprocess_midi_folder

from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit
from tokenizers.trainers import WordLevelTrainer


# =====================
# 설정
# =====================

# MIDI 파일 경로 (수정 필요!)
MIDI_FOLDER = r"C:\Users\Admin\Desktop\Graduation\Sources"

# 데이터셋 저장 경로
DATASET_PATH = os.path.join("datasets", "piano_violin_trackfill")

# 학습 결과 저장 경로
OUTPUT_PATH = os.path.join("training", "piano_violin_trackfill")

# 인코딩 설정
WINDOW_SIZE_BARS = 4      # 한 번에 볼 마디 수
HOP_LENGTH_BARS = 2       # 슬라이딩 간격
DENSITY_BINS_NUMBER = 5   # 밀도 구간 수
TRANSPOSITIONS_TRAIN = list(range(-5, 6))  # 조옮김 범위: -5 ~ +5
TRANSPOSITIONS_VALID = [0]  # 검증용은 조옮김 없이

# 학습 설정
PAD_LENGTH = 768
BATCH_SIZE = 16
EPOCHS = 10


# =====================
# 1단계: 데이터 전처리
# =====================

print("=" * 60)
print("1단계: MIDI 파일 전처리")
print("=" * 60)

# 데이터셋 폴더 생성
if not os.path.exists(DATASET_PATH):
    os.makedirs(DATASET_PATH)

# MIDI → JSON 형식으로 변환
print(f"\nMIDI 폴더: {MIDI_FOLDER}")
songs_data_train, songs_data_valid = preprocess_midi_folder(MIDI_FOLDER, train_ratio=0.8)

print(f"\n학습 데이터: {len(songs_data_train)}개 곡")
print(f"검증 데이터: {len(songs_data_valid)}개 곡")


# =====================
# 2단계: 토큰화
# =====================

print("\n" + "=" * 60)
print("2단계: 토큰 시퀀스 생성")
print("=" * 60)

# Density bins 계산
print("\nDensity bins 계산 중...")
density_bins = get_density_bins(
    songs_data_train,
    WINDOW_SIZE_BARS,
    HOP_LENGTH_BARS,
    DENSITY_BINS_NUMBER
)
print(f"Density bins: {density_bins}")

# 학습 데이터 토큰화 (track_fill 모드)
print("\n학습 데이터 토큰화 중...")
token_sequences_train = encode_songs_data(
    songs_data_train,
    transpositions=TRANSPOSITIONS_TRAIN,
    permute=False,  # 트랙 순서 고정 (피아노 → 바이올린)
    window_size_bars=WINDOW_SIZE_BARS,
    hop_length_bars=HOP_LENGTH_BARS,
    density_bins=density_bins,
    bar_fill=False,
    track_fill=True,       # ⭐ track_fill 모드 활성화
    fill_track_number=1    # ⭐ 바이올린(1번 트랙) 비우기
)
print(f"학습 토큰 시퀀스: {len(token_sequences_train)}개")

# 검증 데이터 토큰화
print("\n검증 데이터 토큰화 중...")
token_sequences_valid = encode_songs_data(
    songs_data_valid,
    transpositions=TRANSPOSITIONS_VALID,
    permute=False,
    window_size_bars=WINDOW_SIZE_BARS,
    hop_length_bars=HOP_LENGTH_BARS,
    density_bins=density_bins,
    bar_fill=False,
    track_fill=True,
    fill_track_number=1
)
print(f"검증 토큰 시퀀스: {len(token_sequences_valid)}개")


# =====================
# 3단계: 파일 저장
# =====================

print("\n" + "=" * 60)
print("3단계: 파일 저장")
print("=" * 60)

# 토큰 시퀀스 저장 함수
def save_token_sequences(token_sequences, path):
    with open(path, "w", encoding="utf-8") as f:
        for token_sequence in token_sequences:
            print(" ".join(token_sequence), file=f)

# 학습 데이터 저장
train_path = os.path.join(DATASET_PATH, "token_sequences_train.txt")
save_token_sequences(token_sequences_train, train_path)
print(f"학습 데이터 저장: {train_path}")

# 검증 데이터 저장
valid_path = os.path.join(DATASET_PATH, "token_sequences_valid.txt")
save_token_sequences(token_sequences_valid, valid_path)
print(f"검증 데이터 저장: {valid_path}")

# 토크나이저 생성 및 저장
print("\n토크나이저 생성 중...")
tokenizer = Tokenizer(WordLevel(unk_token="[UNK]"))
tokenizer.pre_tokenizer = WhitespaceSplit()
trainer = WordLevelTrainer(
    special_tokens=["[UNK]", "[CLS]", "[SEP]", "[PAD]", "[MASK]"]
)
tokenizer.train(files=[train_path, valid_path], trainer=trainer)

tokenizer_path = os.path.join(DATASET_PATH, "tokenizer.json")
tokenizer.save(tokenizer_path)
print(f"토크나이저 저장: {tokenizer_path}")

# Vocab 크기 출력
print(f"Vocab 크기: {tokenizer.get_vocab_size()}")


# =====================
# 4단계: 모델 학습
# =====================

print("\n" + "=" * 60)
print("4단계: 모델 학습")
print("=" * 60)

# 학습 설정
trainer_config = mmmtrainerconfig.MMMTrainerBaseConfig(
    tokenizer_path=tokenizer_path,
    dataset_train_files=[train_path],
    dataset_validate_files=[valid_path],
    pad_length=PAD_LENGTH,
    shuffle_buffer_size=10000,
    batch_size=BATCH_SIZE,
    epochs=EPOCHS,
)

# 학습 시작
trainer = mmmtrainer.MMMTrainer(trainer_config)
trainer.train(
    output_path=OUTPUT_PATH,
    simulate="simulate" in sys.argv
)

print("\n" + "=" * 60)
print("학습 완료!")
print("=" * 60)
print(f"모델 저장 위치: {OUTPUT_PATH}")