"""데이터 모델 (dataclass 기반)."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Transaction:
    id: str
    type: str          # "income" | "expense"
    date: str          # YYYY-MM-DD
    amount: int        # 양수
    category: str
    memo: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class Budget:
    month: str         # YYYY-MM
    amount: int


@dataclass
class Category:
    name: str
