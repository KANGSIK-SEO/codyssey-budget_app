# 파일 기반 가계부 콘솔

## 구조 (모듈 분리)

```
budget_app/
├── __main__.py        # python -m budget_app 진입
├── cli.py             # 인자 파싱 + 명령 디스패치
├── services.py        # 비즈니스 로직 + 검증
├── storage.py         # 파일 I/O (제너레이터 스트리밍, 원자적 교체)
├── models.py          # @dataclass (Transaction/Category/Budget)
└── decorators.py      # 공통 관심사 (예외/시간 측정)
data/                  # 영구 저장 (3개 파일)
├── transactions.jsonl
├── categories.jsonl
└── budgets.jsonl
```

## 핵심 구현 포인트

### 제너레이터 스트리밍

`TransactionStore.stream()`은 파일을 한 줄씩 `yield`. 메모리에 전체 로드 안 함 → 대용량 안전.

`list_recent`/`search`/`export_csv`/`summary` 모두 이 스트림을 그대로 받아 처리.

### 원자적 update/delete

`replace_all`은 임시 파일 → `os.replace`로 원자적 교체. 중간 실패해도 원본 파일 유지.

### 데코레이터로 공통 관심사 분리

`@trace_errors` (`decorators.py`):
- ValueError → 친절한 안내 + exit 2
- FileNotFoundError → 데이터 디렉토리 힌트
- 기타 예외 → 타입+메시지만 출력 (스택트레이스 X)

### 타입 힌트

`Transaction.amount: int`, `tags: List[str]`, 함수 시그니처에 모두 적용 → IDE/타입체커가 계약 검증 가능.

## 실행

```bash
cd budget_app
python3 -m budget_app -h        # 도움말
python3 -m budget_app add        # 대화형 거래 추가
python3 -m budget_app list -limit 10
python3 -m budget_app search -from 2026-05-01 -to 2026-05-31 -category food -q 저녁
python3 -m budget_app summary -month 2026-05 -top 3
python3 -m budget_app budget set -month 2026-05 -amount 100000
python3 -m budget_app category add health
python3 -m budget_app update -id TX-000001 -memo "수정됨"
python3 -m budget_app delete -id TX-000002
python3 -m budget_app export -out export.csv -month 2026-05
python3 -m budget_app import -from import.csv
```

## 저장 포맷

JSONL (1줄=1레코드). 사람이 직접 읽을 수 있고, append-only로 단순.

## CSV 스키마 (import/export)

| column | required | 형식 |
|---|---|---|
| date | Y | YYYY-MM-DD |
| type | Y | income/expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표 구분 |
