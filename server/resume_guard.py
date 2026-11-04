"""Allow a checkpoint continuation for scheduler failures, not arbitrary model errors."""


def can_resume(state: str, exit_code: str, elapsed_seconds: int, limit_minutes: int) -> bool:
    state = state.split()[0].rstrip('+')
    if state in ('TIMEOUT', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL'):
        return True
    return (state == 'FAILED' and exit_code == '143:0' and limit_minutes > 0 and
            elapsed_seconds >= limit_minutes * 60 - 300)
