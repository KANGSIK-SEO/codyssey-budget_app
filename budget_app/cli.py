"""CLI 진입점."""
import argparse
import sys
from typing import List, Optional

from .decorators import trace_errors
from .services import BudgetService, validate_date, validate_type, validate_amount


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="budget_app")
    p.add_argument("-data-dir", dest="data_dir", default="./data")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("add")

    plist = sub.add_parser("list"); plist.add_argument("-limit", type=int, default=10)

    pse = sub.add_parser("search")
    pse.add_argument("-from", dest="date_from"); pse.add_argument("-to", dest="date_to")
    pse.add_argument("-category"); pse.add_argument("-type"); pse.add_argument("-q"); pse.add_argument("-tag")

    psum = sub.add_parser("summary")
    psum.add_argument("-month", required=True); psum.add_argument("-top", type=int, default=3)

    pbud = sub.add_parser("budget"); pbsub = pbud.add_subparsers(dest="bud_cmd", required=True)
    pset = pbsub.add_parser("set"); pset.add_argument("-month", required=True)
    pset.add_argument("-amount", required=True, type=int)

    pcat = sub.add_parser("category"); pcs = pcat.add_subparsers(dest="cat_cmd", required=True)
    pcs.add_parser("list")
    pca = pcs.add_parser("add"); pca.add_argument("name")
    pcr = pcs.add_parser("remove"); pcr.add_argument("name")

    pup = sub.add_parser("update")
    pup.add_argument("-id", dest="tx_id", required=True)
    pup.add_argument("-date"); pup.add_argument("-type"); pup.add_argument("-category")
    pup.add_argument("-amount", type=int); pup.add_argument("-memo")
    pup.add_argument("-tags")  # comma-separated

    pdel = sub.add_parser("delete"); pdel.add_argument("-id", dest="tx_id", required=True)

    pexp = sub.add_parser("export"); pexp.add_argument("-out", required=True)
    pexp.add_argument("-month"); pexp.add_argument("-from", dest="date_from"); pexp.add_argument("-to", dest="date_to")

    pimp = sub.add_parser("import"); pimp.add_argument("-from", dest="in_path", required=True)

    return p.parse_args(argv)


def _input_tx(svc: BudgetService) -> dict:
    print("=== 거래 추가 (대화형) ===")
    date = input("날짜(YYYY-MM-DD): ").strip()
    validate_date(date)
    type_ = input("타입(income/expense): ").strip()
    validate_type(type_)
    cats = svc.categories()
    print(f"카테고리 목록: {', '.join(cats)}")
    category = input("카테고리: ").strip()
    if category not in cats:
        raise ValueError(f"등록되지 않은 카테고리: {category}")
    amount = validate_amount(input("금액(양수 정수): ").strip())
    memo = input("메모(선택, 엔터로 건너뜀): ").strip()
    tags_raw = input("태그(쉼표 구분, 없으면 엔터): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    return {"date": date, "type_": type_, "category": category,
            "amount": amount, "memo": memo, "tags": tags}


@trace_errors
def main(argv: Optional[List[str]] = None):
    if argv is None:
        # 옵션은 sys.argv[1:] 사용
        argv = [a for a in sys.argv[1:] if a != "--profile"]
    ns = _parse_args(argv)
    svc = BudgetService(ns.data_dir)

    if ns.cmd == "add":
        data = _input_tx(svc)
        new_id = svc.add_tx(**data)
        print(f"[저장 완료] id={new_id}")

    elif ns.cmd == "list":
        for tx in svc.list_recent(limit=ns.limit):
            print(f"{tx.id} | {tx.date} | {tx.type:<7} | {tx.category:<10} | "
                  f"{tx.amount:>10} | {tx.memo}")

    elif ns.cmd == "search":
        any_ = False
        for tx in svc.search(date_from=ns.date_from, date_to=ns.date_to,
                             category=ns.category, type_=ns.type, q=ns.q, tag=ns.tag):
            any_ = True
            print(f"{tx.id} | {tx.date} | {tx.type:<7} | {tx.category:<10} | "
                  f"{tx.amount:>10} | {tx.memo}")
        if not any_:
            print("[정보] 결과 없음")

    elif ns.cmd == "summary":
        s = svc.summary(ns.month, top=ns.top)
        if s is None:
            print(f"[정보] {ns.month} 데이터 없음")
        else:
            print(f"총 수입: {s['income']}원")
            print(f"총 지출: {s['expense']}원")
            print(f"잔액:   {s['balance']}원")
            if s["budget"] is not None:
                pct = (s["expense"] / s["budget"]) * 100 if s["budget"] else 0
                warn = " [⚠ 예산 초과]" if s["expense"] > s["budget"] else ""
                print(f"예산:   {s['budget']}원 (사용률 {pct:.1f}%){warn}")
            print(f"\n지출 TOP {ns.top}")
            for i, (cat, amt) in enumerate(s["top"], 1):
                print(f" {i}) {cat} {amt}원")

    elif ns.cmd == "budget":
        if ns.bud_cmd == "set":
            svc.set_budget(ns.month, ns.amount)
            print(f"[저장 완료] {ns.month} 예산 {ns.amount}원")

    elif ns.cmd == "category":
        if ns.cat_cmd == "list":
            for n in svc.categories():
                print(f"- {n}")
        elif ns.cat_cmd == "add":
            ok = svc.add_category(ns.name)
            print(f"[저장 완료] category={ns.name}" if ok else "[정보] 이미 존재함")
        elif ns.cat_cmd == "remove":
            res = svc.remove_category(ns.name)
            print(f"[삭제 완료] category={ns.name}" if res == "OK" else f"[오류] {res}")

    elif ns.cmd == "update":
        changes = {}
        for k in ("date", "type", "category", "amount", "memo"):
            v = getattr(ns, k)
            if v is not None:
                changes[k if k != "type" else "type"] = v
        if ns.tags is not None:
            changes["tags"] = [t for t in ns.tags.split(",") if t]
        if not changes:
            print("[정보] 변경 사항 없음")
        else:
            ok = svc.update_tx(ns.tx_id, **changes)
            print(f"[수정 완료] id={ns.tx_id}" if ok else f"[오류] 없는 id: {ns.tx_id}")

    elif ns.cmd == "delete":
        ok = svc.delete_tx(ns.tx_id)
        print(f"[삭제 완료] id={ns.tx_id}" if ok else f"[오류] 없는 id: {ns.tx_id}")

    elif ns.cmd == "export":
        n = svc.export_csv(ns.out, month=ns.month,
                           date_from=ns.date_from, date_to=ns.date_to)
        print(f"[완료] {ns.out} ({n} records)")

    elif ns.cmd == "import":
        imp, skip = svc.import_csv(ns.in_path)
        print(f"[완료] imported={imp}, skipped={skip}")


if __name__ == "__main__":
    main()
