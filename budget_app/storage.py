"""파일 기반 저장소 — JSONL 스트리밍 (제너레이터)."""
import json
import os
import tempfile
from datetime import datetime
from typing import Iterable, Iterator, List, Optional

from .models import Budget, Category, Transaction


class TransactionStore:
    """transactions.jsonl — append-only.
    update/delete는 임시파일에 재작성 후 원자적 교체로 안정성 확보.
    """

    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "transactions.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self.path):
            open(self.path, "a", encoding="utf-8").close()

    def stream(self) -> Iterator[Transaction]:
        """파일을 한 줄씩 읽어 yield. 메모리에 전체 로드 안 함."""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                yield Transaction(**d)

    def append(self, tx: Transaction) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(tx.__dict__, ensure_ascii=False) + "\n")

    def replace_all(self, txs: Iterable[Transaction]) -> None:
        """원자적 교체: 임시파일 → rename."""
        dirpath = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(prefix="tx_", dir=dirpath)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for tx in txs:
                    f.write(json.dumps(tx.__dict__, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def next_id(self) -> str:
        # 파일 마지막 ID 기반 +1.
        last = 0
        for tx in self.stream():
            try:
                n = int(tx.id.split("-")[-1])
                last = max(last, n)
            except ValueError:
                pass
        return f"TX-{last+1:06d}"


class CategoryStore:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "categories.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self.path):
            # 기본 카테고리 시드
            with open(self.path, "w", encoding="utf-8") as f:
                for n in ["food", "transport", "rent", "salary", "etc"]:
                    f.write(json.dumps({"name": n}) + "\n")

    def list(self) -> List[Category]:
        out: List[Category] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(Category(**json.loads(line)))
        return out

    def names(self) -> List[str]:
        return [c.name for c in self.list()]

    def add(self, name: str) -> bool:
        if name in self.names():
            return False
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"name": name}) + "\n")
        return True

    def remove(self, name: str, used_in_tx: bool) -> str:
        if used_in_tx:
            return "사용 중 카테고리는 삭제할 수 없습니다. 먼저 거래의 카테고리를 변경하세요."
        cats = [c for c in self.list() if c.name != name]
        with open(self.path, "w", encoding="utf-8") as f:
            for c in cats:
                f.write(json.dumps({"name": c.name}) + "\n")
        return "OK"


class BudgetStore:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "budgets.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self.path):
            open(self.path, "a", encoding="utf-8").close()

    def get(self, month: str) -> Optional[int]:
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("month") == month:
                    return int(d["amount"])
        return None

    def set(self, month: str, amount: int) -> None:
        # 같은 월이 있으면 갱신, 없으면 추가
        items = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        replaced = False
        for it in items:
            if it.get("month") == month:
                it["amount"] = amount
                replaced = True
                break
        if not replaced:
            items.append({"month": month, "amount": amount})
        with open(self.path, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
