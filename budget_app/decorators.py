"""공통 관심사 분리 — 예외/시간/로그 데코레이터."""
import functools
import sys
import time
from typing import Callable


def trace_errors(fn: Callable) -> Callable:
    """스택트레이스 대신 원인 + 힌트 출력. 비정상 종료 코드(2)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            print(f"[오류] {e}")
            print("[힌트] 입력 형식을 다시 확인해주세요.")
            sys.exit(2)
        except FileNotFoundError as e:
            print(f"[오류] 파일을 찾을 수 없습니다: {e.filename}")
            print("[힌트] 데이터 디렉토리를 확인하거나 -data-dir 옵션을 사용하세요.")
            sys.exit(2)
        except Exception as e:
            print(f"[오류] {type(e).__name__}: {e}")
            sys.exit(2)
    return wrapper


def timed(label: str = ""):
    """실행 시간 측정 (디버그용; 평소엔 조용)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                dt = (time.perf_counter() - t0) * 1000
                if "--profile" in sys.argv:
                    print(f"[profile] {label or fn.__name__}: {dt:.2f}ms", file=sys.stderr)
        return wrapper
    return deco
