# 파일 기반 가계부 콘솔 프로그램

**미션 번호:** B2-1
**단계:** AI/SW 기초 / Python과 Git 심화
**학습시간:** 60시간 (1.5주)

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
docs/
└── 평가대비_노트.md    # 동료평가 발표·QA 대비
```

## 핵심 구현 포인트

### 제너레이터 스트리밍
`TransactionStore.stream()`은 파일을 한 줄씩 `yield`. 메모리에 전체 로드 안 함 → 대용량 안전.
`list_recent` / `search` / `export_csv` / `summary` 모두 이 스트림을 그대로 받아 처리.

### 원자적 update/delete
`replace_all`은 임시 파일 → `os.replace`로 원자적 교체. 중간 실패해도 원본 파일 유지.

### 데코레이터로 공통 관심사 분리
`@trace_errors` (`decorators.py`):
- ValueError → 친절한 안내 + exit 2
- FileNotFoundError → 데이터 디렉토리 힌트
- 기타 예외 → 타입+메시지만 출력 (스택트레이스 X)

`@timed("label")` — `--profile` 옵션이 있을 때만 stderr로 실행 시간 출력.

### 타입 힌트
`Transaction.amount: int`, `tags: List[str]`, 함수 시그니처에 모두 적용 → IDE/타입체커가 계약 검증 가능.

### 옵션 표기
PDF 스펙이 단일 대시(`-from`)와 이중 대시(`--from`)를 혼용해 표기해서, **두 형태 모두 지원**.
argparse `add_argument("-from", "--from", dest=...)` 패턴.

## 실행

```bash
cd budget_app
python3 -m budget_app -h                                     # 도움말
python3 -m budget_app add                                    # 대화형 거래 추가
python3 -m budget_app list --limit 10
python3 -m budget_app search --from 2026-05-01 --to 2026-05-31 --category food --q 저녁
python3 -m budget_app summary --month 2026-05 --top 3
python3 -m budget_app budget set --month 2026-05 --amount 100000
python3 -m budget_app category add health
python3 -m budget_app update --id TX-000001 --memo "수정됨"
python3 -m budget_app delete --id TX-000002
python3 -m budget_app export --out export.csv --month 2026-05
python3 -m budget_app import --from import.csv
```

## 저장 포맷
JSONL (1줄=1레코드). 사람이 직접 읽을 수 있고, append-only로 단순. 3개 파일로 영구 저장 분리:
- `transactions.jsonl` — 거래 내역
- `categories.jsonl` — 카테고리 목록
- `budgets.jsonl` — 월별 예산

기본 저장 폴더는 `./data`. `--data-dir <path>`로 변경 가능.

## CSV 스키마 (import/export)

| column | required | 형식 |
|---|---|---|
| date | Y | YYYY-MM-DD |
| type | Y | income/expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표 구분 |

공통: UTF-8, 헤더 포함.

## 오류 정책
- 스택트레이스 출력 금지 — `[오류] 원인` + `[힌트] 해결책` 형태로만 출력
- 정상 종료 exit code 0, 오류 종료 exit code 2

## 동료평가 대비
`docs/평가대비_노트.md` 참조. 설계 결정·핵심 데이터 흐름·예상 질문 정리.
