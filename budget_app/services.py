"""비즈니스 로직 — 검증, 검색, 요약."""
import csv
import re
from datetime import datetime
from typing import Iterator, List, Optional

from .models import Transaction
from .storage import BudgetStore, CategoryStore, TransactionStore


def validate_date(s: str) -> str:
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise ValueError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")
    return s


def validate_type(s: str) -> str:
    if s not in ("income", "expense"):
        raise ValueError("type은 income 또는 expense 여야 합니다.")
    return s


def validate_amount(s: str) -> int:
    try:
        n = int(s)
    except ValueError:
        raise ValueError("금액은 정수여야 합니다.")
    if n <= 0:
        raise ValueError("금액은 0보다 커야 합니다.")
    return n


class BudgetService:
    def __init__(self, data_dir: str):
        self.tx = TransactionStore(data_dir)
        self.cat = CategoryStore(data_dir)
        self.bud = BudgetStore(data_dir)

    # ---- 거래 ----
    def add_tx(self, date: str, type_: str, category: str,
               amount: int, memo: str = "", tags: Optional[List[str]] = None) -> str:
        validate_date(date); validate_type(type_);
        if amount <= 0: raise ValueError("금액은 0보다 커야 합니다.")
        if category not in self.cat.names():
            raise ValueError(f"등록되지 않은 카테고리: {category}")
        new_id = self.tx.next_id()
        self.tx.append(Transaction(
            id=new_id, type=type_, date=date, amount=amount,
            category=category, memo=memo, tags=list(tags or []),
        ))
        return new_id

    def list_recent(self, limit: int = 20) -> Iterator[Transaction]:
        # 최신순: 파일 끝에서부터 거꾸로. 메모리 절약을 위해 limit만큼만 버퍼.
        buf: List[Transaction] = []
        for tx in self.tx.stream():
            buf.append(tx)
            if len(buf) > limit * 2:  # date 순 보장 위해 일부 여유
                buf.sort(key=lambda t: (t.date, t.id), reverse=True)
                buf = buf[:limit]
        buf.sort(key=lambda t: (t.date, t.id), reverse=True)
        for tx in buf[:limit]:
            yield tx

    def search(self, *, date_from: Optional[str] = None, date_to: Optional[str] = None,
               category: Optional[str] = None, type_: Optional[str] = None,
               q: Optional[str] = None, tag: Optional[str] = None) -> Iterator[Transaction]:
        for tx in self.tx.stream():
            if date_from and tx.date < date_from: continue
            if date_to and tx.date > date_to: continue
            if category and tx.category != category: continue
            if type_ and tx.type != type_: continue
            if q and q.lower() not in (tx.memo or "").lower(): continue
            if tag and tag not in tx.tags: continue
            yield tx

    def update_tx(self, tx_id: str, **changes) -> bool:
        found = False
        new_list: List[Transaction] = []
        for tx in self.tx.stream():
            if tx.id == tx_id:
                found = True
                self._apply_changes(tx, changes)
            new_list.append(tx)
        if found:
            self.tx.replace_all(new_list)
        return found

    def _apply_changes(self, tx: Transaction, changes: dict) -> None:
        """update_tx의 검증·적용 분리. 단일 책임."""
        for k, v in changes.items():
            if v is None:
                continue
            if k == "date":
                validate_date(v)
            elif k == "type":
                validate_type(v)
            elif k == "amount":
                v = int(v)
                if v <= 0:
                    raise ValueError("금액은 0보다 커야 합니다.")
            elif k == "category":
                if v not in self.cat.names():
                    raise ValueError(f"등록되지 않은 카테고리: {v}")
            setattr(tx, k, v)

    def delete_tx(self, tx_id: str) -> bool:
        found = False
        new_list: List[Transaction] = []
        for tx in self.tx.stream():
            if tx.id == tx_id:
                found = True
                continue
            new_list.append(tx)
        if found:
            self.tx.replace_all(new_list)
        return found

    # ---- 요약 ----
    def summary(self, month: str, top: int = 3) -> Optional[dict]:
        income = expense = 0
        cat_totals: dict = {}
        any_data = False
        for tx in self.tx.stream():
            if not tx.date.startswith(month):
                continue
            any_data = True
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                cat_totals[tx.category] = cat_totals.get(tx.category, 0) + tx.amount
        if not any_data:
            return None
        balance = income - expense
        budget_amount = self.bud.get(month)
        ranked = sorted(cat_totals.items(), key=lambda kv: kv[1], reverse=True)[:top]
        return {
            "month": month, "income": income, "expense": expense, "balance": balance,
            "budget": budget_amount, "top": ranked,
        }

    # ---- 카테고리 ----
    def categories(self):
        return self.cat.names()

    def add_category(self, name: str) -> bool:
        return self.cat.add(name)

    def remove_category(self, name: str) -> str:
        used = any(t.category == name for t in self.tx.stream())
        return self.cat.remove(name, used)

    # ---- 예산 ----
    def set_budget(self, month: str, amount: int):
        if not re.match(r"^\d{4}-\d{2}$", month):
            raise ValueError("month는 YYYY-MM 형식이어야 합니다.")
        if amount <= 0:
            raise ValueError("금액은 0보다 커야 합니다.")
        self.bud.set(month, amount)

    # ---- import/export ----
    def export_csv(self, out_path: str, *, month: Optional[str] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None) -> int:
        gen = self._filtered(month, date_from, date_to)
        count = 0
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "type", "category", "amount", "memo", "tags"])
            for tx in gen:
                w.writerow([tx.date, tx.type, tx.category, tx.amount, tx.memo,
                            ",".join(tx.tags)])
                count += 1
        return count

    def _filtered(self, month, date_from, date_to):
        for tx in self.tx.stream():
            if month and not tx.date.startswith(month): continue
            if date_from and tx.date < date_from: continue
            if date_to and tx.date > date_to: continue
            yield tx

    def import_csv(self, in_path: str) -> tuple:
        imported = 0; skipped = 0
        with open(in_path, "r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    self.add_tx(
                        date=row["date"], type_=row["type"],
                        category=row["category"], amount=int(row["amount"]),
                        memo=row.get("memo", "") or "",
                        tags=[t for t in (row.get("tags", "") or "").split(",") if t],
                    )
                    imported += 1
                except Exception:
                    skipped += 1
        return imported, skipped
