from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PropFirmProfile:
    key: str
    label: str
    firm: str
    account_size: float
    model: str
    step1_profit_target_pct: float
    step2_profit_target_pct: float
    max_daily_loss_pct: float
    max_total_loss_pct: float
    min_trading_days_phase1: int
    min_trading_days_phase2: int
    daily_reference: str
    timezone_label: str = "CE(S)T"


@dataclass
class PropRiskSnapshot:
    profile: str
    balance: float
    equity: float
    day_start_balance: float
    day_start_equity: float
    daily_reference_balance: float
    daily_loss_used: float
    daily_loss_limit: float
    daily_buffer: float
    total_loss_used: float
    total_loss_limit: float
    total_buffer: float
    min_allowed_equity: float
    daily_limit_equity: float
    breached: bool
    soft_breached: bool
    breach_reason: str
    soft_reason: str
    timestamp: str


PROFILES: dict[str, PropFirmProfile] = {
    "ftmo_10k_2step": PropFirmProfile(
        key="ftmo_10k_2step",
        label="FTMO 10K 2-Step",
        firm="FTMO",
        account_size=10_000.0,
        model="2-step",
        step1_profit_target_pct=0.10,
        step2_profit_target_pct=0.05,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        min_trading_days_phase1=4,
        min_trading_days_phase2=4,
        daily_reference="start_of_day_balance",
    ),
    "fundingpips_10k_2step": PropFirmProfile(
        key="fundingpips_10k_2step",
        label="FundingPips 10K 2-Step",
        firm="FundingPips",
        account_size=10_000.0,
        model="2-step",
        step1_profit_target_pct=0.08,
        step2_profit_target_pct=0.05,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        min_trading_days_phase1=3,
        min_trading_days_phase2=3,
        daily_reference="start_of_day_max_balance_equity",
    ),
    "shared_10k_2step": PropFirmProfile(
        key="shared_10k_2step",
        label="Shared 10K 2-Step",
        firm="FTMO + FundingPips",
        account_size=10_000.0,
        model="2-step",
        step1_profit_target_pct=0.10,
        step2_profit_target_pct=0.05,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        min_trading_days_phase1=4,
        min_trading_days_phase2=4,
        daily_reference="start_of_day_max_balance_equity",
    ),
}


def get_profile(profile_key: str = "shared_10k_2step") -> PropFirmProfile:
    return PROFILES.get(profile_key, PROFILES["shared_10k_2step"])


def list_profiles() -> list[dict]:
    return [asdict(profile) for profile in PROFILES.values()]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def trading_day_key(profile: PropFirmProfile, current_time: datetime | None = None) -> str:
    now = current_time or datetime.now(timezone.utc)
    if profile.timezone_label == "CE(S)T":
        local_time = now.astimezone(ZoneInfo("Europe/Prague"))
    else:
        local_time = now.astimezone(timezone.utc)
    return local_time.strftime("%Y-%m-%d")


def compute_prop_risk_snapshot(
    profile: PropFirmProfile,
    *,
    balance: float,
    equity: float,
    day_start_balance: float,
    day_start_equity: float,
    soft_daily_buffer_pct: float = 0.60,
    soft_total_buffer_pct: float = 0.60,
) -> PropRiskSnapshot:
    daily_limit = profile.account_size * profile.max_daily_loss_pct
    total_limit = profile.account_size * profile.max_total_loss_pct

    if profile.daily_reference == "start_of_day_max_balance_equity":
        daily_reference_balance = max(day_start_balance, day_start_equity)
    else:
        daily_reference_balance = day_start_balance

    daily_limit_equity = daily_reference_balance - daily_limit
    min_allowed_equity = profile.account_size - total_limit

    daily_loss_used = max(0.0, daily_reference_balance - equity)
    total_loss_used = max(0.0, profile.account_size - equity)

    daily_buffer = daily_limit - daily_loss_used
    total_buffer = total_limit - total_loss_used

    hard_reason = ""
    if equity <= daily_limit_equity:
        hard_reason = (
            f"Daily loss breached for {profile.label}: "
            f"equity {equity:.2f} <= daily floor {daily_limit_equity:.2f}"
        )
    elif equity <= min_allowed_equity:
        hard_reason = (
            f"Total loss breached for {profile.label}: "
            f"equity {equity:.2f} <= minimum equity {min_allowed_equity:.2f}"
        )

    soft_reason = ""
    if not hard_reason:
        if daily_loss_used >= daily_limit * soft_daily_buffer_pct:
            soft_reason = (
                f"Daily risk at {daily_loss_used / daily_limit:.0%} of limit "
                f"for {profile.label}"
            )
        elif total_loss_used >= total_limit * soft_total_buffer_pct:
            soft_reason = (
                f"Total risk at {total_loss_used / total_limit:.0%} of limit "
                f"for {profile.label}"
            )

    return PropRiskSnapshot(
        profile=profile.key,
        balance=round(balance, 2),
        equity=round(equity, 2),
        day_start_balance=round(day_start_balance, 2),
        day_start_equity=round(day_start_equity, 2),
        daily_reference_balance=round(daily_reference_balance, 2),
        daily_loss_used=round(daily_loss_used, 2),
        daily_loss_limit=round(daily_limit, 2),
        daily_buffer=round(daily_buffer, 2),
        total_loss_used=round(total_loss_used, 2),
        total_loss_limit=round(total_limit, 2),
        total_buffer=round(total_buffer, 2),
        min_allowed_equity=round(min_allowed_equity, 2),
        daily_limit_equity=round(daily_limit_equity, 2),
        breached=bool(hard_reason),
        soft_breached=bool(soft_reason),
        breach_reason=hard_reason,
        soft_reason=soft_reason,
        timestamp=_now_utc(),
    )


def evaluate_phase_targets(
    profile: PropFirmProfile,
    *,
    balance: float,
    trading_days: int,
) -> dict:
    step1_target = profile.account_size * profile.step1_profit_target_pct
    step2_target = profile.account_size * profile.step2_profit_target_pct
    pnl = balance - profile.account_size
    return {
        "profile": profile.key,
        "balance": round(balance, 2),
        "pnl": round(pnl, 2),
        "phase1_target": round(step1_target, 2),
        "phase2_target": round(step2_target, 2),
        "phase1_complete": pnl >= step1_target and trading_days >= profile.min_trading_days_phase1,
        "phase2_complete": pnl >= step2_target and trading_days >= profile.min_trading_days_phase2,
        "phase1_days_remaining": max(0, profile.min_trading_days_phase1 - trading_days),
        "phase2_days_remaining": max(0, profile.min_trading_days_phase2 - trading_days),
    }
